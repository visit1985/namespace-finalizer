import argparse
# noinspection PyCompatibility
from concurrent.futures import ThreadPoolExecutor
import jsonformatter
from kubernetes import client, config, watch
import logging
import os
import time

from example_reconciler import ExampleReconciler

DESCRIPTION = 'An asynchronous pre-delete hook for kubernetes namespaces.'

FINALIZER_NAME = 'example.com/namespace-finalizer'

SYSTEM_NAMESPACES = [
    'kube-node-lease',
    'kube-public',
    'kube-system'
]

LOG_FORMAT = '''{
    "level": "levelname",
    "loggerName": "name",
    "thread": "threadName",
    "message": "message"
}'''

LOG_LEVEL_HELP = 'Change the log-level'
LOG_LEVEL_DEFAULT = 'INFO'


def parse_args():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('-l', '--log-level', dest='log_level', default=LOG_LEVEL_DEFAULT, help=LOG_LEVEL_HELP)
    return parser.parse_args()


def reload_config():
    if 'KUBERNETES_PORT' in os.environ:
        config.load_incluster_config()
    else:
        config.load_kube_config()


def is_system_namespace(event):
    return event['object'].metadata.name in SYSTEM_NAMESPACES


def deletion_in_progress(event):
    return event['object'].metadata.deletion_timestamp


def needs_finalizer(event):
    return not deletion_in_progress(event) and FINALIZER_NAME not in (event['object'].metadata.finalizers or [])


def add_finalizer(event):
    namespace = event['object']
    name = namespace.metadata.name
    logging.info("Adding finalizer %s to namespace %s" % (FINALIZER_NAME, name))
    finalizers = namespace.metadata.finalizers or []
    finalizers.append(FINALIZER_NAME)
    namespace.metadata.finalizers = finalizers
    client.CoreV1Api().patch_namespace(name, namespace)


def remove_finalizer(event):
    name = event['object'].metadata.name
    logging.info("Removing finalizer %s from namespace %s" % (FINALIZER_NAME, name))
    # https://github.com/kubernetes/community/blob/94b696bef96aefba2ca9bf97029694565a84495e/contributors/devel/sig-api-machinery/strategic-merge-patch.md#deletefromprimitivelist-directive
    patch = {"metadata": {"$deleteFromPrimitiveList/finalizers": [FINALIZER_NAME]}}
    client.CoreV1Api().patch_namespace(name, patch)


def needs_reconciliation(event):
    return deletion_in_progress(event) and FINALIZER_NAME in (event['object'].metadata.finalizers or [])


def reconcile(context, event):
    for name, reconciler in context['reconcilers'].items():
        namespace = event['object'].metadata.name
        logging.debug("Running %s for namespace %s" % (name, namespace))
        reconciler.reconcile(namespace)
    remove_finalizer(event)


def handle_event(context, event):
    try:
        logging.debug("Event: %s %s" % (event['type'], event['object'].metadata.name))
        if needs_finalizer(event):
            add_finalizer(event)
            return
        if needs_reconciliation(event):
            reconcile(context, event)
    except (Exception, OSError) as err:
        logging.error("{0}: {1}".format(type(err).__name__, err))


def main():
    args = parse_args()
    jsonformatter.basicConfig(format=LOG_FORMAT, level=logging.getLevelName(args.log_level))
    reload_config()

    context = {
        'reconcilers': {
            'ExampleReconciler': ExampleReconciler()
        }
    }

    v1 = client.CoreV1Api()
    w = watch.Watch()

    logging.info("Listening to stream")
    with ThreadPoolExecutor(max_workers=3) as executor:
        while True:
            try:
                for event in w.stream(v1.list_namespace):
                    if is_system_namespace(event):
                        continue
                    executor.submit(handle_event, context, event)
            except (Exception, OSError) as err:
                logging.error("{0}: {1}".format(type(err).__name__, err))
                time.sleep(5)  # retry timeout
                logging.info("Retry listening to stream")
                # re-instanciate API to refresh credentials
                # https://github.com/kubernetes-client/python/issues/741
                reload_config()
                v1 = client.CoreV1Api()


if __name__ == '__main__':
    try:
        main()
    # gracefully handle keyboard interrupts during tests
    except KeyboardInterrupt:
        print()
