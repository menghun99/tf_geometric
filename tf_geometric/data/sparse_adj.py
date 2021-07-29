# coding=utf-8

import tensorflow as tf
import numpy as np
from tf_geometric.utils.graph_utils import add_self_loop_edge

from tf_geometric.data.graph import Graph

from tf_geometric.nn.kernel.segment import segment_softmax

"""
Sparse Adj for Computation
"""


class SparseAdj(object):

    def __init__(self, edge_index, edge_weight=None, shape=None):
        """
        Sparse Adjacency Matrix for efficient computation.
        :param edge_index:
        :param edge_weight:
        :param shape: [num_rows, num_cols], shape of the adjacency matrix.
        """

        self.edge_index = Graph.cast_edge_index(edge_index)

        edge_index_is_tensor = tf.is_tensor(edge_index)

        if edge_weight is not None:
            self.edge_weight = Graph.cast_edge_weight(edge_weight)
        else:
            if edge_index_is_tensor:
                num_edges = tf.shape(self.edge_index)[1]
                edge_weight = tf.ones([num_edges], dtype=tf.float32)
            else:
                num_edges = np.shape(self.edge_index)[1]
                edge_weight = np.ones([num_edges], dtype=np.float32)
            self.edge_weight = edge_weight

        if shape is None:
            if edge_index_is_tensor:
                num_nodes = tf.reduce_max(edge_index) + 1
            else:
                num_nodes = np.max(edge_index) + 1
            self.shape = [num_nodes, num_nodes]
        else:
            self.shape = shape

    def add_self_loop(self, fill_weight=1.0):
        num_nodes = self.shape[0]
        updated_edge_index, updated_edge_weight = add_self_loop_edge(self.edge_index, num_nodes,
                                                                     edge_weight=self.edge_weight,
                                                                     fill_weight=fill_weight)
        return SparseAdj(updated_edge_index, updated_edge_weight, self.shape)

    def __matmul__(self, h):
        row, col = self.edge_index[0], self.edge_index[1]
        repeated_h = tf.gather(h, col)
        if self.edge_weight is not None:
            repeated_h *= tf.expand_dims(self.edge_weight, axis=-1)
        reduced_h = tf.math.unsorted_segment_sum(repeated_h, row, num_segments=self.shape[0])
        return reduced_h

    def transpose(self):
        row, col = self.edge_index[0], self.edge_index[1]
        transposed_edge_index = tf.stack([col, row], axis=0)
        return SparseAdj(transposed_edge_index, edge_weight=self.edge_weight, shape=self.shape)

    def dropout(self, drop_rate, training=False):
        if training and drop_rate > 0.0:
            edge_weight = tf.compat.v2.nn.dropout(self.edge_weight, drop_rate)
        else:
            edge_weight = self.edge_weight
        return SparseAdj(self.edge_index, edge_weight=edge_weight, shape=self.shape)

    def softmax(self, axis=-1):

        # reduce by row
        if axis == -1 or axis == 1:
            reduce_index = self.edge_index[0]
            num_reduced = self.shape[0]
        # reduce by col
        elif axis == 0 or axis == -2:
            reduce_index = self.edge_index[1]
            num_reduced = self.shape[1]
        else:
            raise Exception("Invalid axis value: {}, axis shoud be -1, -2, 0, or 1".format(axis))

        normed_edge_weight = segment_softmax(self.edge_weight, reduce_index, num_reduced)

        return SparseAdj(self.edge_index, normed_edge_weight, shape=self.shape)

    def __str__(self):
        return "SparseAdj: \n" \
               "edge_index => \n" \
               "{}\n" \
               "edge_weight => {}\n" \
               "shape => {}".format(self.edge_index, self.edge_weight, self.shape)

    def __repr__(self):
        return self.__str__()


# edge_index = [
#     [0, 0, 0, 0, 1, 1, 4, 6],
#     [0, 2, 4, 6, 2, 3, 6, 8]
# ]
#
# adj = SparseAdj(edge_index)
# h = np.random.randn(9, 20).astype(np.float32)
#
# print(adj @ h)
# print(adj.softmax(axis=-1))

