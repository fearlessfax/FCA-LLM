import numpy as np
import pandas as pd
import re
import random
from datetime import date
import json
import asyncio

import fcatng
from fcatng import Context
from shiny import App, reactive, render, ui
from shiny.express.ui import layout_columns

from exploration import Explorer
from eval_prompt import set_prompt,evaluate_prompt,evaluate_prompt_async


app_ui = ui.page_fluid(
    ui.tags.head(
            ui.tags.link(
                rel="stylesheet",
                href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css",
            )
        ),
    ui.tags.style("""
        html, body {
            height: 100%;
            padding: 15px;
            background-color: black;
            color: white;
        }
        #check {
            height: 100%;
        }
    """),
    ui.h1("The FCA LLM Project", style="text-align: center;padding: 10px;"),
    ui.layout_columns(
        ui.card(
            ui.h2("Attribute Exploration", style="text-align: center;"),

            ### INPUT
            ui.navset_pill(
                ui.nav_panel("Input File",
                    ui.div(
                         ui.h5("Input Excel File:",
                               style="""
                                                   display: flex;
                                                   justify-content: center;
                                                   align-items: center;
                                                   margin-bottom: 30px;
                                               """
                               ),
                        ui.div(
                            ui.input_file("file", "", accept=[".xlsx", ".xls"]),
                            style="""
                                       display: flex;
                                       justify-content: center;
                                       align-items: center;
                                       height: 50px;
                                       margin-bottom: 30px;
                                   """
                            ),
                        ),
                    ui.output_ui("rows_column_selector"),
                    ui.output_data_frame("render_dataframe"),

                ),

                ui.nav_panel("Manual Mode",
                    ui.card(
                         ui.div(
                            ui.output_ui("show_current_implication"),
                            ui.layout_columns(
                                ui.h3(""),
                                ui.output_ui("starting_mode_ui"),
                                ui.output_ui("show_implication_buttons"),
                                ui.h3(""),
                                col_widths=(1,5,5,1),
                            ),

                            ui.output_ui("confirm_implication_button_text"),
                            ui.output_ui("reject_implication_button_text"),
                            ui.output_ui("confirm_counter_exp_button"),
                            style="padding-top: 30px; background-color: white; color: black;"
                         ),
                    )
                ),

                ui.nav_panel("Assisted Mode",
                    ui.card(
                         ui.div(
                             ui.output_ui("starting_mode_ui_assisted_mode"),
                             ui.output_ui("show_current_implication_assisted_mode"),
                         ),
                         ui.div(
                             ui.output_ui("show_generation_result_assisted_mode"),
                         ),
                        ui.div(
                            ui.output_ui("show_model_response_accept_button_assisted_mode"),
                            ui.output_ui("show_onclick_reject_buttons"),
                            ui.output_ui("confirm_implication_button_text_assisted_mode"),

                         ),
                    )
                ),

                ui.nav_panel("Automated Mode",
                    ui.card(
                         ui.div(
                             ui.output_ui("starting_mode_ui_auto_mode"),
                             ui.output_ui("show_current_implication_auto_mode"),
                         ),
                         # ui.div(
                         #     ui.output_ui("show_generation_result_auto_mode"),
                         # ),
                        ui.div(
                            ui.output_ui("show_start_exploration_button_auto_mode"),
                            ui.output_ui("show_exploration_log_text_auto_mode"),
                         ),
                    )
                ),
                ui.nav_control(
                    ui.input_action_button("reload_btn", "Reset",class_ ="btn btn-outline-danger")
                ),
                id="tab",
            ),
            ui.tags.script("""
                   document.getElementById("reload_btn").onclick = function() {
                       location.reload();
                   };
               """),
            style="height: 90vh; overflow-y: auto;"
        ),
        ui.card(
            ui.h2("Context Output", style="text-align: center;"),
            ui.card(
                ui.output_data_frame("render_context"),
            ),
            ui.layout_columns(
                ui.card(
                    ui.h6("Active Implications", style="text-align: center;"),
                    ui.output_ui("show_all_implication"),
                ),
                ui.card(
                    ui.h6("Confirmed Implications", style="text-align: center;"),
                    ui.output_ui("show_confirmed_implication"),
                ),
                col_widths=(6, 6)
            ),
            ui.div(
                    ui.download_button("download_df", "Download Context CSV", class_="btn btn-outline-primary",style="text-align: center; font-size: 12px; width: 190px;"),
                        style="""
                                   display: flex;
                                   justify-content: center;
                                   align-items: center;
                               """
            ),
            style="height: 90vh; overflow-y: auto;"
        ),
        col_widths=(6, 6),
    ),
)


def server(input, output, session):

    #####################################################################################
    #                                 CODE FOR AUTO MODE                                #

    models_response_log_auto = reactive.value(None)
    trigger_response = reactive.value(None)

    @output
    @render.ui
    def starting_mode_ui_auto_mode():
        obj = object_state.get()
        if obj is None:
            return ui.div(
                ui.strong(f"Action requires an input file.", style="color: red; margin-top: 100px; margin-left: 30px;"),
                style="margin-top: 30px; margin-left: 24px;"
            )
        else:
            return ui.div("")

    @output
    @render.ui
    def show_current_implication_auto_mode():
        _ = trigger_recalc.get()
        obj = object_state.get()
        if obj is not None:
            implication = obj.Basic_Exploration.get_current_implications()
            return ui.div(
                ui.strong(f"Current Implication : {implication}"),
                style="text-align: center; margin-top: 45px; margin-bottom: 30px;",
            )
        return ui.div("")

    @output
    @render.ui
    def show_start_exploration_button_auto_mode():
        obj = object_state.get()
        if obj is not None:
            return ui.div(
                ui.input_action_button("start_exploration", "Start Exploration", class_="btn-success",
                                          style="margin-top: 10px;width: 250px;", ),
                ui.p("^ Please press the button only once", style="font-size: 12px; margin-top: 10px; margin-bottom: 0px;"),
                ui.p("^ The process will only end once the exploration is complete",style="font-size: 12px;"),
                style="display: flex; flex-direction: column; align-items: center;"
            )
        else:
            return ui.div("")



    @reactive.effect
    @reactive.event(input.start_exploration)
    def set_start_exploration_text():
        if input.start_exploration():
            trigger_response.set("Start")

    @reactive.effect
    def run_exploration():
        if trigger_response.get() == "Start":
            obj = object_state.get()
            if obj is not None:
                print(obj.Basic_Exploration.get_current_implications())
                while obj.Basic_Exploration.get_current_implications() is not None:
                    last_implication = obj.Basic_Exploration.get_current_implications()
                    attributes, objects, values, examples = context_data()
                    premise, conclusion = obj.Basic_Exploration.get_implication_premise_conclusion_for_prompt()

                    prompt = set_prompt(
                        objects=objects,
                        frames=attributes,
                        examples=examples,
                        premise=premise,
                        conclusion=conclusion
                    )

                    result = evaluate_prompt(prompt)

                    if result["output"] == "NO":
                        obj = object_state.get()
                        out = obj.Basic_Exploration.set_counter_example(result["verb"], result["meaning"])

                        if out[0] == "PASS":
                            trigger_recalc.set(trigger_recalc.get() + 1)
                            models_response_log_auto.set(ui.div(models_response_log_auto.get(),
                                    ui.card(
                                        ui.div(
                                            ui.strong(f'For implication : {last_implication}'),
                                            ui.HTML(f"<div>Model suggested that the implication is invalid and</div>"),
                                            ui.HTML(f"<div>Suggested verb: <strong>{result['verb']}</strong></div>"),
                                            ui.HTML(f"<div>With meanings: <strong>{', '.join(result['meaning'])}</strong></div>")
                                        )
                                    )
                                )
                            )
                        else:
                            models_response_log_auto.set(ui.div(models_response_log_auto.get(),
                                    ui.strong(f'For implication : {last_implication}'),
                                    # ui.HTML(f"<div>Model suggested that the implication is invalid and</div>"),
                                    ui.h6("Model Provided a invalid response. and Retried again.", style="color:red; font-weight:bold;"),
                                    ui.h6(out[1], style="color:red;")
                                )
                            )
                    else:
                        trigger_recalc.set(trigger_recalc.get() + 1)
                        obj.Basic_Exploration.post_confirm_implications()
                        models_response_log_auto.set(ui.div(
                            models_response_log_auto.get(),
                            ui.strong(f'For implication : {last_implication}'),
                            ui.h6("Model confirmed the implication.", style="color:blue; font-weight:bold;")
                            )
                        )
            return ui.div("here")
        else:
            return ui.div("")

    @output
    @render.ui
    def show_exploration_log_text_auto_mode():
        model_log = models_response_log_auto.get()
        if model_log is not None:
            return ui.div(
                ui.h6("Exploration completed. The model carried out the following operations:", style="text-align: center; color:green; font-weight:bold; margin-top: 20px;"),
                model_log
            )
        else:
            return ui.div("")


    #####################################################################################
    #                               CODE TO DOWNLOAD CSV                                #

    @output
    @render.download(filename=lambda: f"context-{date.today().isoformat()}-{random.randint(0, 10000)}.csv")
    def download_df():
        obj = object_state.get()
        if obj is None:
            d = {'THE DATAFRAME IS EMPTY': ['PLEASE SET THE CONTEXT FIRST']}
            df = pd.DataFrame(data=d)
            yield df.to_csv()
        else:
            df = obj.Basic_Exploration.get_context_dataframe()
            yield df.to_csv()


    ###################################################################################
    #              CODE FOR TAKING INPUT DATA AND PREPROCESSING FOR CONTEXT           #

    @reactive.calc
    def data():
        file = input.file()
        if not file:
            return None
        return pd.read_excel(file[0]['datapath'], index_col=0)

    @output
    @render.ui
    def rows_column_selector():
        df = data()
        if df is not None:
            df = df.drop(['Example'], axis=1)
            rows, columns = df.shape

            return ui.layout_columns(
                ui.div(
                    ui.h6("Select Rows"),
                    ui.input_slider("row_slider", "", min=1, max=rows, value=[1, 4],),
                    style="display: flex; flex-direction: column; align-items: center;",
                ),
                ui.div(
                    ui.h6("Select Column", style="text-align: center;"),
                    ui.input_slider("column_slider", "", min=1, max=columns, value=[1, 4]),
                    style="display: flex; flex-direction: column; align-items: center;"
                ),
                ui.div(
                    ui.input_action_button("confirm_context", "confirm context", class_="btn-success", style="margin-top: 20px;",),
                ),
                col_widths=(5, 5,2),
            )
        else:
            return ui.div("")

    @output
    @render.data_frame
    def render_dataframe():
        df = data()
        if df is not None:
            start_col, end_col = 1, 4
            start_row, end_row = 1, 4
            if input.row_slider():
                start_row,end_row = input.row_slider()
            if input.row_slider():
                start_col, end_col = input.column_slider()

            object_context_dimensions.set([start_col,end_col,start_row,end_row ])

            df = df.drop(['Example'], axis=1)
            df_reset = df.reset_index()
            return df_reset.iloc[start_row-1:end_row, np.r_[0,start_col:end_col+1]]
        else:
            return pd.DataFrame()

    @reactive.calc
    @reactive.event(input.confirm_context)
    def context_data():
        if input.confirm_context():
            df = data()
            attributes = []
            objects = []
            values = []
            examples = []
            if not df.empty:
                if 'Example' in df.columns:
                    examples = df.loc[:, 'Example']
                    examples = examples.to_list()
                    df = df.drop(['Example'], axis=1)
                df = df.transpose()
                ll = object_context_dimensions.get()
                start_col, end_col , start_row, end_row =ll

                df = df.iloc[start_col-1:end_col,start_row-1:end_row]  # taking out english

                df.columns = df.columns.map(lambda x: x.replace(",", " or") if isinstance(x, str) else x)
                # df.index = df.index.map(lambda x: x.replace("English: ", "") if isinstance(x, str) else x)
                df.index = df.index.map(
                    lambda x: re.sub(r"^[A-Za-z]+:\s*", "", x) if isinstance(x, str) else x
                )
                objects= list(df.index)
                attributes= list(df.columns)
                values = df.values
                values = values.tolist()
                # print(attributes, objects, values)
            return attributes, objects, values , examples
            # return None, None, None
        else:
            return None, None, None, None


    #########################################################################################################
    # BELOW CODE IS FOR DECLARING THE OBJECT AND DISPLAYING THE OUTPUT CONTEXT THIS IS COMMON FOR ALL MODES #

    object_state = reactive.value(None)

    @reactive.effect
    def declare_object():
        attributes, objects , values, _ = context_data()
        if objects is not None:
            obj = Explorer(values, objects, attributes)
            object_state.set(obj)

    @output
    @render.data_frame
    def render_context():
        _ = trigger_recalc.get()
        obj = object_state.get()
        if obj is not None:
            df = obj.Basic_Exploration.get_context_dataframe()
            df_display = df.copy()
            # df_display.columns = [col[:3] + "..." if len(col) > 13 else col for col in df.columns]
            df_reset = df_display.reset_index()
            return df_reset
        return pd.DataFrame()


    ###################################################################################
    #                       BELOW CODE IS FOR THE MANUAL MODE                         #

    object_context_dimensions = reactive.value(None)
    print_implications = reactive.value(None)
    trigger_recalc = reactive.Value(0)
    toggle_state = reactive.Value(True)

    @output
    @render.ui
    def starting_mode_ui():
        obj = object_state.get()
        if obj is None:
            return ui.div(
                ui.strong(f"Action requires an input file.", style="color: red;"),
            )
        else:
            return ui.input_action_button("confirm_implication", "confirm implication", class_="btn-success",
                                          style="margin-top: 20px;width: 250px;", ),

    @output
    @render.ui
    def show_current_implication():
        _ = trigger_recalc.get()
        obj = object_state.get()
        if obj is not None:
            implication = obj.Basic_Exploration.get_current_implications()
            return ui.div(
                ui.strong(f"Current Implication : {implication}"),
                style="text-align: center; margin-top: 20px; margin-bottom: 30px;",
            )
        return ui.div("")

    @output
    @render.ui
    def show_all_implication():
        _ = trigger_recalc.get()
        obj = object_state.get()
        if obj is not None:
            implication = obj.Basic_Exploration.get_attribute_implications()
            return ui.div(
                *[ui.h6(f'{imp}') for imp in implication]
            )
        return ui.div("")

    @output
    @render.ui
    def show_confirmed_implication():
        _ = trigger_recalc.get()
        obj = object_state.get()
        if obj is not None:
            implication = obj.Basic_Exploration.get_confirmed_implications()
            return ui.div(
                *[ui.h6(f'{imp}') for imp in implication]
            )
        return ui.div("")

    @output
    @render.ui
    def confirm_implication_button_text():
        a = print_implications.get()
        if a is not None:
            a = print_implications.get()
            return ui.div(a)
        else:
            return ui.div("")

    @output
    @render.ui
    def show_implication_buttons():
        obj = object_state.get()
        if obj is not None:
            if toggle_state():
                return ui.input_action_button(
                    "toggle_button", "reject implication",
                    class_="btn-warning", style="margin-top: 20px; width: 250px;",
                )
            else:
                return ui.input_action_button(
                    "toggle_button", "confirm counter example",
                    class_="btn-primary", style="margin-top: 20px; width: 250px;"
                )
        else:
            return ui.div("")

    @reactive.effect
    @reactive.event(input.confirm_implication)
    def set_confirm_implication_button_text():
        if input.confirm_implication():
            trigger_recalc.set(trigger_recalc.get() + 1)
            obj = object_state.get()
            if obj is not None:
                toggle_state.set(True)
                obj.Basic_Exploration.post_confirm_implications()
                a = "Previous Implication Confirmed."
                b = ui.h6(f'{a}', style="color: Green; text-align: center; font-weight: bold;")
                print_implications.set(b)
        else:
            print_implications.set("")

    @reactive.effect
    @reactive.event(input.toggle_button)
    def handle_toggle_button_click():
        if toggle_state():
            trigger_recalc.set(trigger_recalc.get() + 1)
            attributes,_,_,_= context_data()
            attr = attributes
            out = ui.div(
                ui.h6(f'Implication Rejected', style="color: Red; text-align: center; font-weight: bold; margin-top: 20px;"),
                ui.h6(f'Provide Counter Example below', style="color: Black; text-align: center; margin-top: 20px; margin-bottom: 20px;"),
                ui.layout_columns(
                    ui.div(
                        ui.h6("Enter Counter Object",style="margin-bottom: 20px;"),
                        ui.input_text("counter_object_text", "", "object"),
                        style="display: flex; flex-direction: column; align-items: center;"
                    ),
                    ui.div(
                        ui.h6("Enter Counter Object's Attributes",style="margin-bottom: 20px;" ),
                        ui.input_checkbox_group(  # <<
                            "counter_attribute_checkbox",  # <<
                            "",
                            attr,
                        ),
                        style="display: flex; flex-direction: column; align-items: center;"
                    ),
                ),
            )
            print_implications.set(out)

        else:
            try:
                obj = object_state.get()
                counter_object = input.counter_object_text()
                counter_attributes = input.counter_attribute_checkbox()
                print(counter_object,counter_attributes)
                out = obj.Basic_Exploration.set_counter_example(counter_object, counter_attributes)
                print(out)
                if out[0] == "PASS":
                    trigger_recalc.set(trigger_recalc.get() + 1)
                    a = "Previous Counter Example has been Confirmed."
                    b = ui.h6(f'{a}', style="color: Blue; text-align: center; font-weight: bold;")
                    print_implications.set(b)
                    print(input.counter_object_text(),input.counter_attribute_checkbox())

                if out[0] == "FAIL":
                    a = "Counter Example is invalid."
                    b = ui.div(
                        ui.h6(f'{a}', style="color: Red; text-align: center; font-weight: bold;"),
                        ui.h6(f'{out[1]}', style="color: Red; text-align: center; font-weight: bold;")
                    )
                    print_implications.set(b)
            except Exception as e:
                _= "-"
        toggle_state.set(not toggle_state())


    ###################################################################################
    #                       BELOW CODE IS FOR THE ASSISTED MODE                         #

    toggle_state_assisted_mode = reactive.Value(True)
    print_implications_assisted_state = reactive.value(None)
    show_buttons_on_reject = reactive.value(False)
    models_response_state = reactive.value(None)

    @output
    @render.ui
    def starting_mode_ui_assisted_mode():
        obj = object_state.get()
        if obj is None:
            return ui.div(
                ui.strong(f"Action requires an input file.", style="color: red; margin-top: 100px; margin-left: 30px;"),
                style="margin-top: 30px; margin-left: 24px;"
            )
        else:
            return ui.div("")

    @output
    @render.ui
    def show_current_implication_assisted_mode():
        _ = trigger_recalc.get()
        obj = object_state.get()
        if obj is not None:
            implication = obj.Basic_Exploration.get_current_implications()
            return ui.div(
                ui.strong(f"Current Implication : {implication}"),
                style="text-align: center; margin-top: 45px; margin-bottom: 30px;",
            )
        return ui.div("")

    @output
    @render.ui
    def show_model_response_accept_button_assisted_mode():
        obj = object_state.get()
        if obj is not None:
            return ui.div(
                ui.div(
                    ui.input_action_button("get_model_response", "Ask the Model", class_="btn btn-outline-primary",
                                           style="margin-top: 20px;", ),
                    ui.p("^ Please wait while the response is being generated. Press the button only once.", style="font-size: 12px; margin-top: 10px; margin-bottom: 0px;"),
                    ui.p("# If the response is unsatisfactory, you may press the button again to regenerate it.",style="font-size: 12px; margin-top: 0px; margin-bottom: 0px;"),

                    style="display: flex; flex-direction: column; align-items: center;"
                ),
                ui.layout_columns(
                    ui.h3(""),
                    ui.div(
                        ui.input_action_button("confirm_model_response", "Confirm Model Response", class_="btn-success",
                                               style="margin-top: 20px;", ),
                        style="display: flex; flex-direction: column; align-items: center;"
                    ),
                    ui.div(
                        ui.input_action_button("reject_model_response", "Reject Model Response", class_="btn-warning",
                                               style="margin-top: 20px;", ),
                        style="display: flex; flex-direction: column; align-items: center;"
                    ),
                    ui.h3(""),
                    col_widths=(1, 5, 5, 1),
                )
            )
        else:
            return ui.div("")

    @output
    @render.ui
    def show_generation_result_assisted_mode():
        model_response = models_response_state.get()
        if model_response is not None:
            # return ui.card(ui.h5("HEY Reached here"))
            result = model_response
            if result['output'] == "YES":
                return ui.card(
                    ui.h5(f"Agents's Response:"),
                    ui.div(f"The agent say's the implication is valid"),
                )
            else:
                return ui.div(
                    ui.h6("Agent's Response:", style="font-weight: bold; margin-bottom: 4px;"),
                    ui.HTML(
                        "<div style='margin-bottom: 0px;'>The agent indicates that the implication is invalid.</div>"),
                    ui.HTML(
                        f"<div style='margin-bottom: 0px;'>Suggested counterexample verb: <strong>{result['verb']}</strong></div>"),
                    ui.HTML(
                        f"<div style='margin-bottom: 0;'>Meaning(s) associated with this verb: <strong>{', '.join(result['meaning'])}</strong></div>"),
                    style="text-align: center;"
                )
        else:
            return ui.div("")

    @reactive.effect
    @reactive.event(input.get_model_response)
    def show_onclick_get_response_buttons():
        obj = object_state.get()
        print_implications_assisted_state.set("")
        show_buttons_on_reject.set(False)
        if obj is not None:
            attributes, objects, values, examples = context_data()
            premise, conclusion = obj.Basic_Exploration.get_implication_premise_conclusion_for_prompt()
            prompt = set_prompt(
                objects=objects,
                frames=attributes,
                examples=examples,
                premise=premise,
                conclusion=conclusion)

            result = evaluate_prompt(prompt)
            models_response_state.set(result)
        else:
            models_response_state.set(None)

    @reactive.effect
    @reactive.event(input.reject_model_response)
    def show_onclick_reject_buttons():
        show_buttons_on_reject.set(True)
        print_implications_assisted_state.set("")

    @reactive.effect
    @reactive.event(input.confirm_model_response)
    def show_onclick_confirm_buttons():
        show_buttons_on_reject.set(False)
        toggle_state_assisted_mode.set(True)

        model_response = models_response_state.get()
        if model_response is not None:
            if model_response['output'] == "NO":
                obj = object_state.get()
                counter_example_verb = model_response["verb"]
                counter_example_meanings = model_response["meaning"]
                out = obj.Basic_Exploration.set_counter_example(counter_example_verb, counter_example_meanings)
                if out[0] == "PASS":
                    trigger_recalc.set(trigger_recalc.get() + 1)
                    a = "Previous Model Response Confirmed, Counter Examples added."
                    b = ui.h6(f'{a}', style="color: Blue; text-align: center; font-weight: bold;")
                    print_implications_assisted_state.set(b)
                    # print(input.counter_object_text(), input.counter_attribute_checkbox())

                if out[0] == "FAIL":
                    a = "Previous Model Response is invalid, Please generate model response again."
                    b = ui.div(
                        ui.h6(f'{a}', style="color: Red; text-align: center; font-weight: bold;"),
                        ui.h6(f'{out[1]}', style="color: Red; text-align: center; font-weight: bold;")
                    )
                    print_implications_assisted_state.set(b)

                print_implications_assisted_state.set(b)
                models_response_state.set(None)
            else:
                trigger_recalc.set(trigger_recalc.get() + 1)
                obj = object_state.get()
                obj.Basic_Exploration.post_confirm_implications()
                a = "Previous Model Response Confirmed, Implication confirmed."
                b = ui.h6(f'{a}', style="color: Blue; text-align: center; font-weight: bold;")
                print_implications_assisted_state.set(b)
                models_response_state.set(None)
        else:
            print_implications_assisted_state.set("")

    @output
    @render.ui
    def show_onclick_reject_buttons():
        if show_buttons_on_reject():
            if toggle_state_assisted_mode():
                reject = ui.input_action_button(
                    "toggle_button_assisted_mode", "reject implication",
                    class_="btn btn-outline-warning", style="margin-top: 20px; width: 250px;",
                )
            else:
                reject = ui.input_action_button(
                    "toggle_button_assisted_mode", "confirm counter example",
                    class_="btn btn-outline-primary", style="margin-top: 20px; width: 250px;")

            a = ui.div(
                ui.h6("Provide Manual Input:", style="text-align:center;font-weight: bold; margin-bottom: 4px;"),
                ui.layout_columns(
                    ui.h3(""),
                    ui.input_action_button("confirm_implication_assisted_mode", "confirm implication",
                                           class_="btn btn-outline-success",
                                           style="margin-top: 20px;width: 250px;", ),
                    reject,
                    ui.h3(""),
                    col_widths=(1, 5, 5, 1),
                ))
            return a
        else:
            return ui.div("")

    @reactive.effect
    @reactive.event(input.toggle_button_assisted_mode)
    def handle_toggle_button_click():
        if toggle_state_assisted_mode():
            trigger_recalc.set(trigger_recalc.get() + 1)
            attributes, _, _, _ = context_data()
            attr = attributes
            out = ui.div(
                ui.h6(f'Implication Rejected',
                      style="color: Red; text-align: center; font-weight: bold; margin-top: 20px;"),
                ui.h6(f'Provide Counter Example below',
                      style="color: Black; text-align: center; margin-top: 20px; margin-bottom: 20px;"),
                ui.layout_columns(
                    ui.div(
                        ui.h6("Enter Counter Object", style="margin-bottom: 20px;"),
                        ui.input_text("counter_object_text_assisted_mode", "", "object"),
                        style="display: flex; flex-direction: column; align-items: center;"
                    ),
                    ui.div(
                        ui.h6("Enter Counter Object's Attributes", style="margin-bottom: 20px;"),
                        ui.input_checkbox_group(  # <<
                            "counter_attribute_checkbox_assisted_mode",  # <<
                            "",
                            attr,
                        ),
                        style="display: flex; flex-direction: column; align-items: center;"
                    ),
                ),
            )
            print_implications_assisted_state.set(out)

        else:
            try:
                obj = object_state.get()
                counter_object = input.counter_object_text_assisted_mode()
                counter_attributes = input.counter_attribute_checkbox_assisted_mode()
                # print(counter_object, counter_attributes)
                out = obj.Basic_Exploration.set_counter_example(counter_object, counter_attributes)
                # print(out)
                if out[0] == "PASS":
                    trigger_recalc.set(trigger_recalc.get() + 1)
                    a = "Previous Counter Example has been Confirmed."
                    b = ui.h6(f'{a}', style="color: Blue; text-align: center; font-weight: bold;")
                    print_implications_assisted_state.set(b)
                    # print(input.counter_object_text(), input.counter_attribute_checkbox())

                if out[0] == "FAIL":
                    a = "Counter Example is invalid."
                    b = ui.div(
                        ui.h6(f'{a}', style="color: Red; text-align: center; font-weight: bold;"),
                        ui.h6(f'{out[1]}', style="color: Red; text-align: center; font-weight: bold;")
                    )
                    print_implications_assisted_state.set(b)
            except Exception as e:
                _ = "-"
        toggle_state_assisted_mode.set(not toggle_state_assisted_mode())

    @reactive.effect
    @reactive.event(input.confirm_implication_assisted_mode)
    def set_confirm_implication_button_text():
        if input.confirm_implication_assisted_mode():
            trigger_recalc.set(trigger_recalc.get() + 1)
            obj = object_state.get()
            if obj is not None:
                toggle_state_assisted_mode.set(True)
                obj.Basic_Exploration.post_confirm_implications()
                a = "Previous Implication Confirmed."
                b = ui.h6(f'{a}', style="color: Green; text-align: center; font-weight: bold;")
                print_implications_assisted_state.set(b)
        else:
            print_implications_assisted_state.set("")

    @output
    @render.ui
    def confirm_implication_button_text_assisted_mode():
        a = print_implications_assisted_state.get()
        if a is not None:
            a = print_implications_assisted_state.get()
            return ui.div(a)
        else:
            return ui.div("")

app = App(app_ui, server)