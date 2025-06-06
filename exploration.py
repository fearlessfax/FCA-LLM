import fcatng
import copy
import re
from fcatng import Context
from fcatng.partial_context import PartialContext
import pandas as pd
import numpy as np
from openai import OpenAI
import ast

class ExplorationException(Exception):
    pass

class WrongCounterExample(ExplorationException):
    pass

class BasisConflict(ExplorationException):
    def __init__(self, set_):
        self.set = set_

    def __str__(self):
        return "{0} conflict with confirmed implications".format(self.set)


class NotCounterExamplePremise(WrongCounterExample):

    def __init__(self, set_, implication):
        self.set = set_
        self.implication = implication

    def __str__(self):
        output = "{0} is not counter example to {1}. ".format(self.set,
                                                              self.implication)
        output += "Counter example doesn't contain all elements from premise"
        return output


class NotCounterExampleConclusion(WrongCounterExample):

    def __init__(self, set_, implication):
        self.set = set_
        self.implication = implication

    def __str__(self):
        output = "{0} is not counter example to {1}. ".format(self.set,
                                                              self.implication)
        output += "Counter example intent contains all elements from " \
                  "conclusion"
        return output


class BasicExploration(object):

    context = None
    attribute_implications = None
    object_implications = None
    confirmed_attribute_implications = None
    confirmed_object_implications = None

    def __init__(self, initial_cxt):
        self.context = copy.deepcopy(initial_cxt)
        self._init_implications()

    def _init_implications(self):

        self.attribute_implications = fcatng.compute_dg_basis(self.context)
        transposed_cxt = self.context.transpose()
        self.object_implications = fcatng.compute_dg_basis(transposed_cxt)
        self.confirmed_attribute_implications = []
        self.confirmed_object_implications = []

    def recompute_basis(self):
        basis = self.confirmed_attribute_implications
        new_implications = fcatng.compute_dg_basis(self.context, imp_basis=basis)
        self.attribute_implications = []
        for imp in new_implications:
            if imp not in basis:
                self.attribute_implications.append(imp)

        basis = self.confirmed_object_implications
        transposed_cxt = self.context.transpose()

        new_implications = fcatng.compute_dg_basis(transposed_cxt, imp_basis=basis)
        self.object_implications = []
        for imp in new_implications:
            if imp not in basis:
                self.object_implications.append(imp)

    def confirm_attribute_implication(self, imp_index):
        imp = self.attribute_implications[imp_index]
        self.confirmed_attribute_implications.append(imp)
        del self.attribute_implications[imp_index]

    def confirm_object_implication(self, imp_index):
        imp = self.object_implications[imp_index]
        self.confirmed_object_implications.append(imp)
        del self.object_implications[imp_index]

    def counter_example_for_attr_implication(self, name, intent, imp_index):
        implication = self.attribute_implications[imp_index]
        premise = implication.premise
        conclusion = implication.conclusion

        if (premise & intent) != premise:
            raise NotCounterExamplePremise(intent, implication)

        if (conclusion & intent) == conclusion:
            raise NotCounterExampleConclusion(intent, implication)

        if not self.check_intent_for_conflicts(intent):
            raise BasisConflict(intent)

        self.context.add_object_with_intent(intent, name)

        self.recompute_basis()

    def counter_example_for_obj_implication(self, name, extent, imp_index):
        implication = self.object_implications[imp_index]
        premise = implication.premise
        conclusion = implication.conclusion

        if (premise & extent) != premise:
            raise NotCounterExamplePremise(extent, implication)

        if (conclusion & extent) == conclusion:
            raise NotCounterExampleConclusion(extent, implication)

        if not self.check_extent_for_conflicts(extent):
            raise BasisConflict(extent)

        self.context.add_attribute_with_extent(extent, name)
        self.recompute_basis()

    def check_extent_for_conflicts(self, extent):
        for imp in self.confirmed_object_implications:
            if (imp.premise & extent) != imp.premise:
                continue
            if (imp.conclusion & extent) == imp.conclusion:
                continue
            return False

        return True

    def check_intent_for_conflicts(self, intent):
        for imp in self.confirmed_attribute_implications:
            if (imp.premise & intent) != imp.premise:
                continue
            if (imp.conclusion & intent) == imp.conclusion:
                continue
            return False

        return True

    def add_object(self, intent, name):
        if not check_intent_for_conflicts(intent):
            raise BasisConflict(intent)
        else:
            self.context.add_object_with_intent(intent, name)
            self.recompute_basis()

    def add_attribute(self, extent, name):
        if not check_extent_for_conflicts(extent):
            raise BasisConflict(extent)
        else:
            self.context.add_attribute_with_extent(extent, name)
            self.recompute_basis()

    def edit_attribute(self, new_extent, name):
        if not check_extent_for_conflicts(extent):
            raise BasisConflict(extent)
        else:
            self.context.set_attribute_extent(extent, name)
            self.recompute_basis()

    def edit_object(self, new_intent, name):
        if not check_intent_for_conflicts(intent):
            raise BasisConflict(intent)
        else:
            self.context.set_object_intent(intent, name)
            self.recompute_basis()

    def get_current_implications(self):
        implication = ""
        if len(self.attribute_implications) != 0:
            implication += str(self.attribute_implications[0])
            current_implication = [line for line in implication.strip().split('\n')]
            return current_implication[0]
        else:
            return None

    def get_attribute_implications(self):
        return self.attribute_implications

    def get_confirmed_implications(self):
        return self.confirmed_attribute_implications

    def post_confirm_implications(self):
        if len(self.attribute_implications) != 0:
            self.confirm_attribute_implication(0)

    def get_context_dataframe(self):
        str_context = str(self.context)
        context_2d = [line.split(',') for line in str_context.strip().split('\n')]

        attribute_columns = context_2d[0]
        object_index = context_2d[1]

        context_list = [attribute_columns]

        for i in range(2, len(context_2d)):
            a = str(context_2d[i])
            result = list(a)[2:-2]
            context_list.append(result)
        context_np = np.array(context_list)
        df2 = pd.DataFrame(context_np[1:], index=object_index, columns=context_list[0])
        return df2

    def set_counter_example(self,object,attribute):
        try:
            self.counter_example_for_attr_implication(object, set(attribute), 0)
            return "PASS", "PASS"
        except Exception as e:
            return "FAIL", e

    def get_implication_premise_conclusion_for_prompt(self):
        implication = self.attribute_implications[0]
        premise = implication.premise
        conclusion = implication.conclusion - implication.premise
        return list(premise), list(conclusion)

class Explorer:
    def __init__(self, values, objects, attributes):
        self.context = Context(values, objects, attributes)
        self.Basic_Exploration = BasicExploration(self.context)

