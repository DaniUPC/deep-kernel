import tensorflow as tf

from kernels import KernelFunction


def example_layout_fn(x, **params):
    hidden = _fully_connected(x, 256)
    return _fully_connected(hidden, 10)


def kernel_example_layout_fn(x, **params):
    kernel = KernelFunction()
    hidden = _fully_connected(x, 256)
    hidden_kernel = kernel.apply_kernel(hidden, dims=256)
    return _fully_connected(hidden_kernel, 10, activation_fn=None)


def _fully_connected(x, outputs, activation_fn=tf.nn.relu):
    return tf.contrib.layers.fully_connected(
        x,
        outputs,
        activation_fn=activation_fn,
        variables_collections=[tf.GraphKeys.WEIGHTS]
    )