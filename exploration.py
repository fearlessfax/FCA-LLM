import fcatng
import copy
import re
from fcatng import Context
from fcatng.partial_context import PartialContext
import pandas as pd
import numpy as np
from openai import OpenAI
import ast

##existing Implementation
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
    """
    Exploration class for basic exploration algorithm
    """

    context = None
    attribute_implications = None
    object_implications = None
    confirmed_attribute_implications = None
    confirmed_object_implications = None

    def __init__(self, initial_cxt):
        """Exploration starts with some initial context - *initial_cxt*"""
        self.context = copy.deepcopy(initial_cxt)
        # After initializing of context we need to compute initial implications
        self._init_implications()

    def __repr__(self):
        output = ""
        output += "Context:\n"
        output += "========\n"
        output += str(self.context) + "\n"
        output += "Attribute implications:\n"
        output += "=======================\n"
        if not self.attribute_implications:
            output += "empty\n"
        for imp in self.attribute_implications:
            output += str(imp) + "\n"
            if (imp == ''):
                output += "NULLLLLL" + "\n"
        output += "Confirmed attribute implications:\n"
        output += "=================================\n"
        for imp in self.confirmed_attribute_implications:
            output += str(imp) + "\n"
        output += "Object implications:\n"
        output += "====================\n"
        for imp in self.object_implications:
            output += str(imp) + "\n"
        output += "Confirmed object implications:\n"
        output += "==============================\n"
        for imp in self.confirmed_object_implications:
            output += str(imp) + "\n"
        return output

    def _init_implications(self):
        """Compute stem base for initial context"""
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

        ## this part is erroring out
        ### i think this part is looking towards improving the object implications
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

        # first we need to check that it is actually the counter example
        # counter example intent should contain all attributes from premise
        if (premise & intent) != premise:
            raise NotCounterExamplePremise(intent, implication)

        # Counterexample intent should contain NOT all attributes from
        # conclusion
        if (conclusion & intent) == conclusion:
            raise NotCounterExampleConclusion(intent, implication)

        if not self.check_intent_for_conflicts(intent):
            raise BasisConflict(intent)

            # if counter example is correct, we add new object to context
        # and recompute stem base with confirmed implications as basis
        self.context.add_object_with_intent(intent, name)

        # ------ this line of code is causing issue
        self.recompute_basis()

    def counter_example_for_obj_implication(self, name, extent, imp_index):
        implication = self.object_implications[imp_index]
        premise = implication.premise
        conclusion = implication.conclusion

        # first we need to check that it is actually the counter example
        # counter example intent should contain all attributes from premise
        if (premise & extent) != premise:
            raise NotCounterExamplePremise(extent, implication)

        # Counterexample intent should contain NOT all attributes from
        # conclusion
        if (conclusion & extent) == conclusion:
            raise NotCounterExampleConclusion(extent, implication)

        if not self.check_extent_for_conflicts(extent):
            raise BasisConflict(extent)

        # if counter example is correct, we add new attribute to context
        # and recompute stem base with confirmed implications as basis
        self.context.add_attribute_with_extent(extent, name)
        self.recompute_basis()

    def check_extent_for_conflicts(self, extent):
        """
        Checks new attribute with *extent* for conflicts with confirmed
        object implications. Return True if all is ok.
        """
        for imp in self.confirmed_object_implications:
            if (imp.premise & extent) != imp.premise:
                continue
            if (imp.conclusion & extent) == imp.conclusion:
                continue
            return False

        return True

    def check_intent_for_conflicts(self, intent):
        """
        Checks new object with *intent* for conflicts with confirmed
        attribute implications. Return True if all is ok.
        """
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
            return "None"

    def get_attribute_implications(self):
            # output = ""
            # output += " Attribute implications:\n"
            # output += "=======================\n"
            # for imp in self.attribute_implications:
            #     output += str(imp) + "\n"
        return self.attribute_implications

    def get_confirmed_implications(self):
        # output = ""
        # output += "Confirmed attribute implications:\n"
        # output += "=================================\n"
        # for imp in self.confirmed_attribute_implications:
        #     output += str(imp) + "\n"
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

    def start_exploration(self, attr_example):

        # while(len(obj.attribute_implications) != 0):
        for i in range(1):
            str_context = str(self.context)
            context_2d = [line.split(',') for line in str_context.strip().split('\n')]
            objects = context_2d[1]
            objects = ', '.join(objects)

            implication = ""
            implication += str(self.attribute_implications[0])
            each_implication = [line.split('=>') for line in implication.strip().split('\n')]
            current_implication = [line for line in implication.strip().split('\n')]

            prompt = ""
            prompt += f'We have the following word meaning list: \n{attr_example}\n'
            prompt += "already checked verbs : " + objects + " , segment"

            prompt += "\n\nCheck the following hypothesis:\n"
            prompt += "Is it true that every verb with the meaning"
            hypothesis = [line.strip() for line in each_implication[0][0].split(',')]
            conclusion = [line.strip() for line in each_implication[0][1].split(',')]

            hypothesis_prompt = ''
            for i in range(len(hypothesis)):
                hypothesis_prompt += f' "{hypothesis[i]}"'
                if i < len(hypothesis) - 1: hypothesis_prompt += " and "
            prompt += hypothesis_prompt
            prompt += " also has the meanings "
            for i in range(len(conclusion)):
                prompt += f' "{conclusion[i]}"'
                if i < len(conclusion) - 1: prompt += " and "
            prompt += """

    if the hypothesis is valid, then output: 'YES',

    If it is not valid, then output: 'NO', 

    If it is not valid, then output a counterexample verb that is not in the already checked verb list and it's meanings 

    the counterexample verb must only have the meanings from the word meaning list and also it should atleast mean"""

            prompt += f'{hypothesis_prompt} and include it also in the meanings list'
            prompt += '''

    return output in following json format
    {
    "output":YES/NO
    "verb":
    "meaning": 
    }'''
            # print(prompt)
            print("Current implication : ", current_implication[0])
            result = self.evalulate_promt(prompt)
            print("\nAgent's response : ")
            print(result)
            print("-------------------")

            match = re.search(r'\{.*\}', result, re.DOTALL)
            if match:
                result_s = match.group(0)
            else:
                print("No match found.")
            result_d = ast.literal_eval(result_s)

            if result_d['output'] == "YES":
                print("\n-> The agent agrees")
                inp = input("\n-> Do you want to confirm the implecation ? 1/0")
                if int(inp) == 1:
                    self.confirm_attribute_implication(0)
                    print("\n-> The implication has been confirmed")

            elif result_d['output'] == "NO":
                print("\n-> The agent disagrees")
                print("\n-> NOW we have to Give a counter example")
                print("\nthe agent suggests the following verb : ", result_d['verb'])
                print("\nwith the following attributes to the verb :\n\n", result_d['meaning'])
                a = int(input("do you want to try to add this : 1/0"))
                try:
                    if a == 1:
                        self.counter_example_for_attr_implication(result_d['verb'], set(result_d['meaning']), 0)
                except:
                    print("An exception occurred")

            inp = input("\n-> Do you want to exit the system ? 1/0")
            if int(inp) == 1:
                print("\n-> Exited......")
                break
            print("\n----------------------------------------------------------------\n")

    # def evalulate_promt(self,prompt):
    #
    #     client = OpenAI(base_url="https://llm.scads.ai/v1", api_key=my_api_key)
    #     models = []
    #     for model in client.models.list().data:
    #         models.append(model.id)
    #
    #     model_name = "meta-llama/Llama-3.3-70B-Instruct"
    #
    #     response = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model=model_name)
    #     Response1 = response.choices[0].message.content
    #
    #     response2 = client.chat.completions.create(
    #         messages=[{"role": "user", "content": str(Response1) + " extract the json from this response"}],
    #         model=model_name)
    #     Response2 = response2.choices[0].message.content
    #     return Response2

class Explorer:
    def __init__(self, values, objects, attributes):
        self.context = Context(values, objects, attributes)
        self.Basic_Exploration = BasicExploration(self.context)