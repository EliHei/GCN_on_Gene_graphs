from layers import *


class Model(object):
    def __init__(self, **kwargs):
        allowed_kwargs = {'name', 'logging'}
        for kwarg in kwargs.keys():
            assert kwarg in allowed_kwargs, 'Invalid keyword argument: ' + kwarg
        name = kwargs.get('name')
        if not name:
            name = self.__class__.__name__.lower()
        self.name = name

        logging = kwargs.get('logging', False)
        self.logging = logging

        self.vars = {}
        self.placeholders = {}

        self.layers = []
        self.activations = []

        self.inputs = None
        self.outputs = None

        self.loss = 0
        self.accuracy = 0
        self.optimizer = None
        self.opt_op = None

    def _build(self):
        raise NotImplementedError

    def build(self):
        """ Wrapper for _build() """
        with tf.variable_scope(self.name):
            self._build()

        # Build sequential layer model
        self.activations.append(self.inputs)
        for layer in self.layers:
            hidden = layer(self.activations[-1])
            # print(hidden.shape)
            self.activations.append(hidden)
        self.outputs = self.activations[-1]

        # Store model variables for easy access
        variables = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.name)
        self.vars = {var.name: var for var in variables}

        # Build metrics
        self._loss()
        self._accuracy()
        self.opt_op = self.optimizer.minimize(self.loss)

    def predict(self):
        pass

    def _loss(self):
        raise NotImplementedError

    def _accuracy(self):
        raise NotImplementedError

    def save(self, sess=None):
        if not sess:
            raise AttributeError("TensorFlow session not provided.")
        saver = tf.train.Saver(self.vars)
        save_path = saver.save(sess, "tmp/%s.ckpt" % self.name)
        print("Model saved in file: %s" % save_path)

    def load(self, sess=None):
        if not sess:
            raise AttributeError("TensorFlow session not provided.")
        saver = tf.train.Saver(self.vars)
        save_path = "tmp/%s.ckpt" % self.name
        saver.restore(sess, save_path)
        print("Model restored from file: %s" % save_path)


class SimpleGCN(Model):
    def __init__(self, placeholders, input_dim, num_class, **kwargs):
        super(SimpleGCN, self).__init__(**kwargs)
        self.input_dim = input_dim
        self.inputs = placeholders['features']
        # self.input_dim = self.inputs.get_shape().as_list()[1]  # To be supported in future Tensorflow versions
        self.placeholders = placeholders
        self.num_class = num_class
        self.optimizer = tf.train.AdamOptimizer(learning_rate=FLAGS.learning_rate)

        self.build()

    def _loss(self):
        # Weight decay loss
        for var in self.layers[0].vars.values():
            self.loss += FLAGS.weight_decay * tf.nn.l2_loss(var)

        self.loss += self.placeholders['weight'] * tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=self.outputs, labels=self.placeholders['labels']))

    def _accuracy(self):
        correct_prediction = tf.equal(tf.argmax(self.outputs, 1), tf.argmax(self.placeholders['labels']))
        self.accuracy = tf.reduce_mean(tf.cast(correct_prediction, dtype=tf.float32))

    def _build(self):
        self.layers.append(GraphConvolution(input_dim=self.input_dim,
                                            output_dim=FLAGS.hidden1,
                                            placeholders=self.placeholders,
                                            act=tf.nn.relu,
                                            dropout=True,
                                            sparse_inputs=True,
                                            is_cheby=False))

        # self.layers.append(GraphConvolution(input_dim=FLAGS.hidden1,
        #                                     output_dim=FLAGS.hidden2,
        #                                     placeholders=self.placeholders,
        #                                     act=tf.nn.relu,
        #                                     dropout=True,
        #                                     is_cheby=False))
        #
        # self.layers.append(GraphConvolution(input_dim=FLAGS.hidden2,
        #                                     output_dim=FLAGS.hidden3,
        #                                     placeholders=self.placeholders,
        #                                     act=tf.nn.relu,
        #                                     dropout=True,
        #                                     is_cheby=False))

        self.layers.append(SumLayer())
        self.layers.append(Dense(input_dim=FLAGS.hidden1,
                                 output_dim=self.num_class,
                                 placeholders=self.placeholders,
                                 dropout=True,
                                 act=lambda x: x))

    def predict(self):
        return tf.argmax(self.outputs, 1)


class CheybyGCN(Model):
    def __init__(self, placeholders, input_dim, num_class, locality=None, **kwargs):
        super(CheybyGCN, self).__init__(**kwargs)
        self.input_dim = input_dim
        self.inputs = placeholders['features']
        # self.input_dim = self.inputs.get_shape().as_list()[1]  # To be supported in future Tensorflow versions
        self.placeholders = placeholders
        self.locality = locality
        self.num_class = num_class
        self.optimizer = tf.train.AdamOptimizer(learning_rate=FLAGS.learning_rate)

        self.build()

    def _loss(self):
        # Weight decay loss
        for var in self.layers[0].vars.values():
            self.loss += FLAGS.weight_decay * tf.nn.l2_loss(var)

        self.loss += self.placeholders['weight'] * tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=self.outputs, labels=self.placeholders['labels']))

    def _accuracy(self):
        correct_prediction = tf.equal(tf.argmax(self.outputs, 1), tf.argmax(self.placeholders['labels']))
        self.accuracy = tf.reduce_mean(tf.cast(correct_prediction, dtype=tf.float32))

    def _build(self):
        self.layers.append(GraphConvolution(input_dim=self.input_dim,
                                            output_dim=FLAGS.hidden1,
                                            placeholders=self.placeholders,
                                            act=tf.nn.relu,
                                            dropout=True,
                                            sparse_inputs=True,
                                            locality=self.locality[0]))

        self.layers.append(GraphConvolution(input_dim=FLAGS.hidden1,
                                            output_dim=FLAGS.hidden2,
                                            placeholders=self.placeholders,
                                            act=tf.nn.relu,
                                            dropout=True,
                                            locality=self.locality[1]))

        self.layers.append(GraphConvolution(input_dim=FLAGS.hidden2,
                                            output_dim=FLAGS.hidden3,
                                            placeholders=self.placeholders,
                                            act=tf.nn.relu,
                                            dropout=True,
                                            locality=self.locality[2]))

        self.layers.append(SumLayer())
        self.layers.append(Dense(input_dim=FLAGS.hidden3,
                                 output_dim=self.num_class,
                                 placeholders=self.placeholders,
                                 dropout=True,
                                 act=lambda x: x))

    def predict(self):
        return tf.argmax(self.outputs, 1)
