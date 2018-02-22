#!/usr/bin/env python3

# ------------------------------------------------------------------------
# Copyright (C) 2016-2017 Andrzej Pronobis - All Rights Reserved
#
# This file is part of LibSPN. Unauthorized use or copying of this file,
# via any medium is strictly prohibited. Proprietary and confidential.
# ------------------------------------------------------------------------

import tensorflow as tf
import numpy as np
from itertools import product, chain
from context import libspn as spn
import time
import argparse
import colorama as col
import sys
from tensorflow.python.client import timeline
import os
import random
col.init()

red = col.Fore.RED
blue = col.Fore.BLUE
green = col.Fore.GREEN
yellow = col.Fore.YELLOW
magenta = col.Fore.MAGENTA
cyan = col.Fore.CYAN
white = col.Fore.WHITE


def print1(str, file, color=yellow):
    if file:
        print(str, file=file)
    print(color + str + col.Style.RESET_ALL)


def print2(str, file):
    if file:
        print(str, file=file)
    print(blue + str + col.Style.RESET_ALL)


class Ops:

    def product(inputs, num_inputs, num_input_cols, num_prods, inf_type,
                indices=None, log=False, output=None):
        p = []
        for inps, n_inp_cols in zip(inputs, num_input_cols):
            num_inputs = len(inps)
            # Create permuted indices based on number and size of inputs
            inds = map(int, np.arange(n_inp_cols))
            permuted_inds = list(product(inds, repeat=num_inputs))
            permuted_inds_list = [list(elem) for elem in permuted_inds]
            permuted_inds_list_of_list = []
            for elem in permuted_inds_list:
                permuted_inds_list_of_list.append([elem[i:i+1] for i in
                                                   range(0, len(elem), 1)])

            # Create inputs list by combining inputs and indices
            permuted_inputs = []
            for indices in permuted_inds_list_of_list:
                permuted_inputs.append([tuple(i) for i in zip(inps, indices)])

            # Generate 'n_prods' Product nodes, connecting each to its inputs
            for perm_inps in permuted_inputs:
                p = p + [spn.Product(*perm_inps)]

        # Connect all product nodes to a single root Sum node and generate its
        # weights
        root = spn.Sum(*p)
        root.generate_weights()

        if log:
            value_op = root.get_log_value(inference_type=inf_type)
        else:
            value_op = root.get_value(inference_type=inf_type)

        return spn.initialize_weights(root), value_op

    def perm_products(inputs, num_inputs, num_input_cols, num_prods, inf_type,
                      indices=None, log=False, output=None):
        if indices is not None:
            # Create inputs list with indices
            inputs = [[(inp, ind) for inp, ind in zip(inps, inds)] for inps, inds
                      in zip(inputs, indices)]

        # Generate 'len(inputs)' PermProducts nodes, modeling 'n_prods' products
        # within each
        p = [spn.PermProducts(*inps) for inps in inputs]

        # Connect all PermProducts nodes to a single root Sum node and generate
        # its weights
        root = spn.Sum(*p)
        root.generate_weights()

        if log:
            value_op = root.get_log_value(inference_type=inf_type)
        else:
            value_op = root.get_value(inference_type=inf_type)

        return spn.initialize_weights(root), value_op

    def products(inputs, num_inputs, num_input_cols, num_prods, inf_type,
                 indices=None, log=False, output=None):
        p = []
        # Generate 'len(inputs)' Products node, modelling 'n_prods' ∈ 'num_prods'
        # products within each
        for inps, n_inp_cols, n_prods in zip(inputs, num_input_cols, num_prods):
            num_inputs = len(inps)
            # Create permuted indices based on number and size of inps
            inds = map(int, np.arange(n_inp_cols))
            permuted_inds = list(product(inds, repeat=num_inputs))
            permuted_inds_list = [list(elem) for elem in permuted_inds]
            permuted_inds_list_of_list = []
            for elem in permuted_inds_list:
                permuted_inds_list_of_list.append([elem[i:i+1] for i in
                                                   range(0, len(elem), 1)])

            # Create inputs-list by combining inps and indices
            permuted_inputs = []
            for indices in permuted_inds_list_of_list:
                permuted_inputs.append([tuple(i) for i in zip(inps, indices)])
            permuted_inputs = list(chain.from_iterable(permuted_inputs))

            # Generate a single Products node, modeling 'n_prods' product nodes
            # within, connecting it to inputs
            p = p + [spn.Products(*permuted_inputs, num_prods=n_prods)]

        # Connect all product nodes to a single root Sum node and generate its
        # weights
        root = spn.Sum(*p)
        root.generate_weights()

        if log:
            value_op = root.get_log_value(inference_type=inf_type)
        else:
            value_op = root.get_value(inference_type=inf_type)

        return spn.initialize_weights(root), value_op

    def products_layer(inputs, num_inputs, num_input_cols, num_prods, inf_type,
                       indices=None, log=False, output=None):
        products_inputs = []
        num_or_size_prods = []
        if isinstance(inputs, list):  # Is a list of ContVars inputs - Multiple inputs
            for inps, n_inp_cols, n_prods in zip(inputs, num_input_cols, num_prods):
                num_inputs = len(inps)
                # Create permuted indices based on number and size of inputs
                inds = map(int, np.arange(n_inp_cols))
                permuted_inds = list(product(inds, repeat=num_inputs))
                permuted_inds_list = [list(elem) for elem in permuted_inds]
                permuted_inds_list_of_list = []
                for elem in permuted_inds_list:
                    permuted_inds_list_of_list.append([elem[i:i+1] for i in
                                                       range(0, len(elem), 1)])

                # Create inputs list by combining inputs and indices
                permuted_inputs = []
                for indices in permuted_inds_list_of_list:
                    permuted_inputs.append([tuple(i) for i in zip(inps, indices)])
                products_inputs += list(chain.from_iterable(permuted_inputs))

                # Create products-size list
                num_or_size_prods += [num_inputs] * n_prods
        else:  # Is a single input of type ContVars - A single input
            outer_offset = 0
            permuted_inds_list = []
            for n_inps, n_inp_cols in zip(num_inputs, num_input_cols):
                # Create permuted indices based on number and size of inputs
                inds = map(int, np.arange(n_inp_cols))
                permuted_inds = list(product(inds, repeat=n_inps))
                offsets = np.array(list(range(0, (n_inps * n_inp_cols), n_inp_cols))) + outer_offset
                outer_offset += n_inps * n_inp_cols
                for perm_inds in permuted_inds:
                    permuted_inds_list.append([p_ind + os for p_ind, os in
                                               zip(list(perm_inds), offsets)])

            # Content of list object 'perm_inds' needs to be of type int, if not
            # input_parser in Input class complains
            products_inputs = [(inputs, list(map(int, perm_inds))) for perm_inds
                               in permuted_inds_list]
            num_or_size_prods = [len(perm_inds) for perm_inds in permuted_inds_list]

        # Generate a single ProductsLayer node, modeling 'sum(num_prods)' products
        # within, connecting it to inputs
        p = spn.ProductsLayer(*products_inputs, num_or_size_prods=num_or_size_prods)

        # Connect all product nodes to a single root Sum node and generate its
        # weights
        root = spn.Sum(p)
        root.generate_weights()

        if log:
            value_op = root.get_log_value(inference_type=inf_type)
        else:
            value_op = root.get_value(inference_type=inf_type)

        return spn.initialize_weights(root), value_op


class OpTestResult:
    """Result of a single test of a single op."""

    def __init__(self, op_name, on_gpu, graph_size, indices, single_input,
                 setup_time, run_times, output_correct):
        self.op_name = op_name
        self.on_gpu = on_gpu
        self.graph_size = graph_size
        self.indices = indices
        self.single_input = single_input
        self.setup_time = setup_time
        self.run_times = run_times
        self.output_correct = output_correct


class TestResults:
    """Results for a single test for multiple ops and devices."""

    def __init__(self, test_name, cpu_results, gpu_results):
        self.test_name = test_name
        self.cpu_results = cpu_results
        self.gpu_results = gpu_results

    def print(self, file):
        def get_header(dev):
            return ("%3s %11s %5s %5s %13s %11s %15s %14s %10s" %
                    (dev, 'op', 'size', 'indices', 'single_input', 'setup_time',
                     'first_run_time', 'rest_run_time', 'correct'))

        def get_res(res):
            """Helper function printing a single result."""
            return ("%15s %5d %5s %10s %14.2f %15.2f %14.2f %10s" %
                    (res.op_name, res.graph_size, res.indices, res.single_input,
                     res.setup_time * 1000, res.run_times[0] * 1000,
                     np.mean(res.run_times[1:]) * 1000, res.output_correct))

        # Print results
        print1("\n-----------------------", file)
        print1("%s" % self.test_name, file)
        print1("-----------------------", file)
        print1(get_header("CPU"), file)
        for res in sorted(self.cpu_results, key=lambda x: len(x.op_name)):
            print1(get_res(res), file, (red if res.op_name is "product" else
                   magenta if res.op_name is "products" else
                   (blue if res.single_input is "Yes" else cyan) if res.op_name
                   is "products_layer" else (green if res.indices is "No" else white)))

        print1(get_header("GPU"), file)
        for res in sorted(self.gpu_results, key=lambda x: len(x.op_name)):
            print1(get_res(res), file, (red if res.op_name is "product" else
                   magenta if res.op_name is "products" else
                   (blue if res.single_input is "Yes" else cyan) if res.op_name
                   is "products_layer" else (green if res.indices is "No" else white)))


class PerformanceTest:

    def __init__(self, num_inputs, batch_size, num_input_cols, num_ops, num_runs,
                 without_cpu, without_gpu, without_product, without_products,
                 without_indices, without_single_input, log_devs, profile,
                 profiles_dir, file):
        self.num_inputs = num_inputs
        self.batch_size = batch_size
        self.num_input_cols = num_input_cols
        self.num_prods = [pow(n_inp_cols, n_inps) for n_inps, n_inp_cols in
                          zip(num_inputs, num_input_cols)]
        self.num_ops = num_ops
        self.num_runs = num_runs
        self.without_cpu = without_cpu
        self.without_gpu = without_gpu
        self.without_product = without_product
        self.without_products = without_products
        self.without_indices = without_indices
        self.without_single_input = without_single_input
        self.log_devs = log_devs
        self.profile = profile
        self.profiles_dir = profiles_dir
        self.file = file
        self.test_failed = False

        print1("Params:", file)
        print1("- num_inputs=%s" % num_inputs, file)
        print1("- batch_size=%s" % batch_size, file)
        print1("- num_input_cols=%s" % num_input_cols, file)
        print1("- num_prods=%s" % self.num_prods, file)
        print1("- num_ops=%s" % num_ops, file)
        print1("- num_runs=%s" % num_runs, file)
        print1("", file=file)

    def _true_output(self, inputs, indices=None, inf_type=None):
        if inf_type == spn.InferenceType.MARGINAL:
            np_sum_op = np.sum
        elif inf_type == spn.InferenceType.MPE:
            np_sum_op = np.amax
        else:
            sys.exit('ERROR: Incorrect inference type: ', inf_type)

        products_output = []

        for inps, n_inps, n_inp_cols in zip(inputs, self.num_inputs,
                                            self.num_input_cols):
            # Create permuted indices based on number and size of inputs
            inds = map(int, np.arange(n_inp_cols))
            permuted_inds = list(product(inds, repeat=n_inps))
            off_sets = list(range(0, (n_inps * n_inp_cols), n_inp_cols))
            permuted_inds_list = []
            for perm_inds in permuted_inds:
                permuted_inds_list.append([p_ind + off_set for p_ind, off_set in
                                           zip(list(perm_inds), off_sets)])

            concatenated_inputs = np.concatenate(inps, axis=1)
            products_output.append(np.concatenate([np.prod(concatenated_inputs[:, p_inds],
                                                  axis=1, keepdims=True) for p_inds
                                                  in permuted_inds_list], axis=1))

        products_output = np.concatenate(products_output, axis=1)
        root_weight = 1.0 / sum(self.num_prods)
        return np_sum_op(products_output * root_weight, axis=1, keepdims=True)

    def _run_op_test(self, op_fun, inputs, indices=None, single_input=False,
                     log=False, on_gpu=True, inf_type=spn.InferenceType.MARGINAL):
        """Run a single test for a single op."""
        # Preparations
        op_name = op_fun.__name__
        device_name = '/gpu:0' if on_gpu else '/cpu:0'

        # Print
        print2("--> %s: on_gpu=%s, num_inputs=%s, inputs_shape=%s, inference=%s, log=%s"
               % (op_name, on_gpu, self.num_inputs, inputs[0][0].shape, ("MPE" if
                  inf_type == spn.InferenceType.MPE else "MARGINAL"), log),
               self.file)

        # Compute true output
        true_out = self._true_output(inputs, indices, inf_type)

        # Create graph
        tf.reset_default_graph()
        with tf.device(device_name):
            # Create inputs
            if single_input:
                num_inputs_array = np.array(self.num_inputs)
                num_input_cols_array = np.array(self.num_input_cols)
                num_vars = int(np.sum(num_inputs_array * num_input_cols_array))
                inputs_pl = spn.ContVars(num_vars=num_vars)
            else:
                inputs_pl = [[spn.ContVars(num_vars=n_inp_cols) for _ in
                              range(n_inps)] for n_inps, n_inp_cols in
                             zip(self.num_inputs, self.num_input_cols)]
            # Create ops
            start_time = time.time()
            init_ops, ops = op_fun(inputs_pl, self.num_inputs, self.num_input_cols,
                                   self.num_prods, inf_type, indices, log)
            setup_time = time.time() - start_time
        # Get num of graph ops
        graph_size = len(tf.get_default_graph().get_operations())
        # Run op multiple times
        output_correct = True
        with tf.Session(config=tf.ConfigProto(
                allow_soft_placement=False,
                log_device_placement=self.log_devs)) as sess:
            # Initialize weights of all the sum nodes in the graph
            init_ops.run()
            # Create feed dictionary
            if single_input:
                feed = {inputs_pl: np.concatenate(list(chain(*inputs)), axis=1)}
            else:
                feed = {inp_pl: inp for inp_pl, inp in zip(chain(*inputs_pl),
                                                           chain(*inputs))}
            run_times = []
            for n in range(self.num_runs):
                # Run
                start_time = time.time()
                out = sess.run(ops, feed_dict=feed)
                run_times.append(time.time() - start_time)
                # Test value
                try:
                    np.testing.assert_array_almost_equal(out, (np.log(true_out)
                                                         if log else true_out))
                except AssertionError:
                    output_correct = False
                    self.test_failed = True

            if self.profile:
                # Add additional options to trace the session execution
                options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
                run_metadata = tf.RunMetadata()

                out = sess.run(ops, feed_dict=feed, options=options,
                               run_metadata=run_metadata)

                # Create the Timeline object, and write it to a json file
                fetched_timeline = timeline.Timeline(run_metadata.step_stats)
                chrome_trace = fetched_timeline.generate_chrome_trace_format()
                if not os.path.exists(self.profiles_dir):
                    os.makedirs(self.profiles_dir)

                file_name = op_name
                file_name += ("_GPU" if on_gpu else "_CPU")
                file_name += ("_MPE-LOG" if log else "_MPE") if inf_type == \
                    spn.InferenceType.MPE else ("_MARGINAL-LOG" if log else
                                                "_MARGINAL")

                with open('%s/timeline_value_%s.json' % (self.profiles_dir,
                          file_name), 'w') as f:
                    f.write(chrome_trace)

        # Return stats
        return OpTestResult(op_name, on_gpu, graph_size, ("No" if (op_fun is
                            Ops.perm_products and indices is None) else "Yes"),
                            ("Yes" if (op_fun is Ops.products_layer and single_input
                             is True) else "No"), setup_time, run_times,
                            output_correct)

    def _run_test(self, test_name, op_funs, inputs, indices, inf_type, log):
        """Run a single test for multiple ops and devices."""
        cpu_results = []
        gpu_results = []
        for op_fun in op_funs:
            if not self.without_cpu:
                cpu_results.append(
                    self._run_op_test(op_fun, inputs, indices=None,
                                      single_input=False, log=log, on_gpu=False,
                                      inf_type=inf_type))
                # PermProds with indices
                if op_fun is Ops.perm_products and not self.without_indices:
                        cpu_results.append(
                            self._run_op_test(op_fun, inputs, indices,
                                              single_input=False, log=log,
                                              on_gpu=False, inf_type=inf_type))
                # ProductsLayer with single-input
                if op_fun is Ops.products_layer and not self.without_single_input:
                        cpu_results.append(
                            self._run_op_test(op_fun, inputs, indices=None,
                                              single_input=True, log=log,
                                              on_gpu=False, inf_type=inf_type))
            if not self.without_gpu:
                gpu_results.append(
                    self._run_op_test(op_fun, inputs, indices=None,
                                      single_input=False, log=log, on_gpu=True,
                                      inf_type=inf_type))
                # PermProds with indices
                if op_fun is Ops.perm_products and not self.without_indices:
                        gpu_results.append(
                            self._run_op_test(op_fun, inputs, indices,
                                              single_input=False, log=log,
                                              on_gpu=True, inf_type=inf_type))
                # ProductsLayer with single-input
                if op_fun is Ops.products_layer and not self.without_single_input:
                        gpu_results.append(
                            self._run_op_test(op_fun, inputs, indices=None,
                                              single_input=True, log=log,
                                              on_gpu=True, inf_type=inf_type))
        return TestResults(test_name, cpu_results, gpu_results)

    def run(self):
        """Run all tests."""
        print1("Running tests:", self.file)
        results = []

        inputs = [[np.random.rand(self.batch_size, n_inp_cols) for _ in
                  range(n_inps)] for n_inps, n_inp_cols in zip(self.num_inputs,
                  self.num_input_cols)]
        indices = [[random.sample(range(n_inp_cols), k=n_inp_cols) for _ in
                    range(n_inps)] for n_inps, n_inp_cols in
                   zip(self.num_inputs, self.num_input_cols)]

        r = self._run_test('InferenceType: MARGINAL',
                           [] + ([Ops.product] if not self.without_product else [])
                           + ([Ops.products] if not self.without_products else [])
                           + [Ops.perm_products, Ops.products_layer],
                           inputs, indices, inf_type=spn.InferenceType.MARGINAL,
                           log=False)
        results.append(r)

        r = self._run_test('InferenceType: MARGINAL-LOG',
                           [] + ([Ops.product] if not self.without_product else [])
                           + ([Ops.products] if not self.without_products else [])
                           + [Ops.perm_products, Ops.products_layer],
                           inputs, indices, inf_type=spn.InferenceType.MARGINAL,
                           log=True)
        results.append(r)

        # Print results
        for res in results:
            res.print(self.file)

        if self.test_failed:
            print("\n ATLEAST ONE TEST FAILED!")


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--num-inputs', default=[3] * 10, type=list,
                        help="Num of input nodes")
    parser.add_argument('--batch-size', default=1000, type=int,
                        help="Num of rows of inputs")
    parser.add_argument('--num-input-cols', default=[5] * 10, type=list,
                        help="Num of cols of inputs")
    parser.add_argument('--num-runs', default=50, type=int,
                        help="Number of times each test is run")
    parser.add_argument('--log-devices', action='store_true',
                        help="Log on which device op is run. Affects run time!")
    parser.add_argument('--without-cpu', action='store_true',
                        help="Do not run CPU tests")
    parser.add_argument('--without-gpu', action='store_true',
                        help="Do not run GPU tests")
    parser.add_argument('--without-product', action='store_true',
                        help="Do not run tests for Product")
    parser.add_argument('--without-products', action='store_true',
                        help="Do not run tests for Products")
    parser.add_argument('--without-indices', action='store_true',
                        help="Do not run test cases for PermProds with indices")
    parser.add_argument('--without-single-input', action='store_true',
                        help="Do not run test cases for ProductsLayer with single-input")
    parser.add_argument('--profile', default=False, action='store_true',
                        help="Run test one more time and profile")
    parser.add_argument('--profiles-dir', default='profiles', type=str,
                        help="Run test one more time and profile")
    parser.add_argument('--save-to', default='', type=str,
                        help="Save results to file")
    args = parser.parse_args()

    # Atleast two inputs are needed for modelling multiple products in PermProducts
    if not all(n_inp >= 2 for n_inp in args.num_inputs):
        sys.exit('ERROR: All num_inputs must be >= 2')

    # Atleast two columns per input are needed for modelling multiple products
    # in PermProducts
    if not all(n_inp_cols >= 2 for n_inp_cols in args.num_input_cols):
        sys.exit('ERROR: All num_input_cols must be >= 2')

    # Atleast two inputs are needed for modelling multiple products in PermProducts
    if len(args.num_inputs) != len(args.num_input_cols):
        sys.exit('Lengths of num_inputs and num_input_cols must be the same!')

    # Open a file
    f = None
    if args.save_to:
        f = open(args.save_to, 'w')

    try:
        t = PerformanceTest(args.num_inputs, args.batch_size, args.num_input_cols,
                            len(args.num_inputs), args.num_runs, args.without_cpu,
                            args.without_gpu, args.without_product,
                            args.without_products, args.without_indices,
                            args.without_single_input, args.log_devices,
                            args.profile, args.profiles_dir, f)
        t.run()
    finally:
        if f is not None:
            f.close()


if __name__ == '__main__':
    main()
