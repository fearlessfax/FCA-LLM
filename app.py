import fcatng
import numpy as np
from fcatng import Context
import pandas as pd
import re
from datetime import date
import random
from shiny import App, reactive, render, ui
from exploration import Explorer


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

                ### MANUAL MODE
                ui.nav_panel("Manual Mode",
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
                ),
                ui.nav_panel("Assisted Mode"),
                ui.nav_panel("Automated Mode"),
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


    #CODE TO DOWNLOAD CSV
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

    #CODE FOR TAKING INPUT DATA AND PREPROCESSING FOR CONTEXT
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

            if not df.empty:
                if 'Example' in df.columns:
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
            return attributes, objects, values
            # return None, None, None
        else:
            return None, None, None



    ###################################################################################
    #                       BELOW CODE IS FOR THE MANUAL MODE                         #
    ###################################################################################

    object_context_dimensions = reactive.value(None)
    object_state = reactive.value(None)
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

    @reactive.effect
    def declare_object():
        attributes, objects , values = context_data()
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
            attributes,_,_= context_data()
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

app = App(app_ui, server)