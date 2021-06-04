import logging
import os


class ExampleReconciler:
    # noinspection PyMethodMayBeStatic
    def reconcile(self, namespace):
        logging.info("Running ExampleReconciler for namespace {}".format(namespace))
        # TODO: Your custom code here!


def main():
    logging.basicConfig(level=logging.getLevelName('INFO'))

    reconciler = ExampleReconciler()
    namespace = os.environ.get('NAMESPACE', 'default')
    reconciler.reconcile(namespace)


if __name__ == '__main__':
    main()
