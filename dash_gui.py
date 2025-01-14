import dash_bootstrap_components as dbc
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import serial
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo 
import os
import csv

# Initialize serial connection
SERIAL_PORT = '/dev/ttyUSB0' #'COM4' #
BAUD_RATE = 115200

def get_time_now():
    """Returns the current timestamp in microseconds."""
    return int(time.time() * 1_000_000)

def create_new_save_folder():
    """
    Creates a new log file in the format logs/<date>.log.
    Creates the logs directory if it doesn't exist.q
    Returns the path to the log file.
    """
    # Get the current date
    log_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".log"
    
    # Define the folder and file path
    folder_path = os.path.join("logs")
    os.makedirs(folder_path, exist_ok=True)  # Create the directory if it doesn't exist
    
    # Define the log file path
    file_path = os.path.join(folder_path, log_name)
    
    # Create an empty log file if it doesn't exist
    if not os.path.exists(file_path):
        with open(file_path, 'w') as log_file:
            log_file.write("")  # Create an empty file
    
    return file_path

def init_data():
    global log_path, time_start, serial_data, description
    print("Initing data")

    log_path = create_new_save_folder()
    time_start = get_time_now()
    serial_data = {"timestamps": [], "delta_times": [], "indices": [], "temperatures": []}
    description = ""

init_data()


def update_log(serial_data):
    """
    Overwrites the log file with the latest serial_data in CSV format.
    Columns: index, timestamp, delta_times, temp1, temp2, temp3, temp4
    """

    try:
        # Open the log file in write mode (overwrites the file)
        with open(log_path, 'w', newline='') as log_file:
            writer = csv.writer(log_file, delimiter=";")
            
            # Write the CSV header
            header = ["index", "timestamp", "delta_times", "temp1", "temp2", "temp3", "temp4"]
            writer.writerow(header)
            
            # Write each row of serial_data
            for idx, time, delta_time, temps in zip(
                serial_data["indices"],
                serial_data["timestamps"],
                serial_data["delta_times"],
                serial_data["temperatures"]
            ):
                # Ensure temps has 4 values (fill with None if fewer)
                temps = temps + [None] * (4 - len(temps))
                # Write the row
                writer.writerow([
                    idx,
                    format_microseconds_to_human(time),
                    delta_time,
                    temps[0],
                    temps[1],
                    temps[2],
                    temps[3]
                ])
    except Exception as e:
        print(f"Error writing to log file: {e}")



def format_microseconds_to_human(microseconds):
    """Converts microseconds to human readable format with one millisecond precision."""
    # Convert microseconds to seconds
    seconds = microseconds / 1_000_000
    # Create a naive datetime object (without timezone)
    dt = datetime.fromtimestamp(seconds)
    # Format as ISO 8601 and round milliseconds to one decimal place
    return dt.strftime("%Y-%m-%d %H:%M:%S") + f".{int(dt.microsecond / 100000)}"



def get_last_60_seconds(serial_data):
    """Returns the last 60 seconds of data from serial_data."""

    if not serial_data["delta_times"]:
        #print("no delta times uwu", serial_data)
        return None

    # Find the cutoff delta_time (most recent - 60 seconds)
    latest_delta_time = serial_data["delta_times"][-1]
    cutoff_delta_time = latest_delta_time - 60*1000

    # Filter the data
    filtered_data = {
        "indices": [],
        "temperatures": [],
        "timestamps": [],
        "delta_times": []
    }

    for i in range(len(serial_data["delta_times"])):
        if serial_data["delta_times"][i] >= cutoff_delta_time:
            filtered_data["indices"].append(serial_data["indices"][i])
            filtered_data["temperatures"].append(serial_data["temperatures"][i])
            filtered_data["timestamps"].append(serial_data["timestamps"][i])
            filtered_data["delta_times"].append(serial_data["delta_times"][i])

    return filtered_data


def read_serial_data():
    """Reads and parses serial data."""
    global serial_data
    
    try:
        print("Reading serial")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        while True:
            line = ser.readline().decode('utf-8').strip()
            if line and len(line) > 1:
                #print("Serial read:", line)

                parts = line.split(' ')
                if len(parts) > 2:
                    try:
                        index = int(parts[0])  # Extract index
                        temps = "".join(parts[1:])
                        temps_parts = temps.split(';')[:-1]
                        if len(temps_parts) == 4:
                            temperatures = [float(temp) for temp in temps_parts if temp]
                            timestamp = get_time_now()
                            delta_time = timestamp - time_start
                            delta_time = int(delta_time / 1000)

                            # Append index and temperatures to the data structure
                            serial_data["indices"].append(index)
                            serial_data["temperatures"].append(temperatures)
                            serial_data["timestamps"].append(timestamp)
                            serial_data["delta_times"].append(delta_time)

                            print(f"Temps: {temperatures}", "len", len(serial_data["indices"]))
                            update_log(serial_data)
                    except Exception as e:
                        print("Error reading serial: ", e)
            else:
                time.sleep(0.2)

    except Exception as e:
        print(f"Error reading serial: {e}")

# Start a background thread to read serial data
threading.Thread(target=read_serial_data, daemon=True).start()

# Dash app setup
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

app.layout = html.Div([
    dcc.Graph(id='temperature-graph', style={'height': '70vh'}),
    dbc.Row(
        [
            dbc.Col(html.Span(f"Saved at: {log_path}", id="saved-path", style={"verticalAlign": "middle"})),
            dbc.Col(dbc.Button("Clear and start a new record", color="primary", id='start-button', n_clicks=0, className="me-1"))
        ]
    , className="m-2"),
    dash_table.DataTable(
        id='temperature-table',
        style_table={'height': '30vh', 'overflowY': 'auto', 'width': '100%'},
        style_cell={
            'textAlign': 'center',
            'minWidth': '50px',
            'maxWidth': '200px',
            'whiteSpace': 'normal',
        },
        style_header={'fontWeight': 'bold', 'backgroundColor': 'lightgrey'},
    ),
    dbc.Row(
        [
            dbc.Col(
                dcc.Input(
                    id="text-input",
                    type="text",
                    placeholder="Enter text to save...",
                    style={"width": "100%"}
                ),
                width=9
            ),
            dbc.Col(
                html.Button("Save", id="save-button", n_clicks=0, className="btn btn-primary"),
                width=3
            ),
        ],
        className="m-2"
    ),
    dcc.Interval(id='interval-component', interval=1000, n_intervals=0)  # Update every second
], style={'display': 'flex', 'flexDirection': 'column'})


n_clicks_old = 0
@app.callback(
    [
        Output('temperature-graph', 'figure'),
        Output('temperature-table', 'data'),
        Output('temperature-table', 'columns'),
        Output('saved-path', 'children'),
        Output('text-input', 'value')
    ],
    [
        Input('start-button', 'n_clicks'),
        State('text-input', 'value'),
        Input('interval-component', 'n_intervals'),
    ],
    [
        State('temperature-table', 'data'), 
        #State('text-input', 'value')
    ]
)
def update_content(n_clicks, description_value, n_intervals, current_data):
    global n_clicks_old, n_clicks_save_old, serial_data, description

    description = description_value

    if n_clicks != n_clicks_old:
        n_clicks_old = n_clicks
        init_data()  # restart data

    serial_data_graph = get_last_60_seconds(serial_data)

    if serial_data_graph is None:
        # Placeholder for empty data
        figure = go.Figure(
            layout=go.Layout(
                title="Waiting for data...",
                xaxis_title="Delta Time (s)",
                yaxis_title="Temperature (°C)"
            )
        )
        return figure, [], [{"name": "Index", "id": "Index"}], f"Saved at: {log_path}", description

    else:
        # Prepare graph
        figure = go.Figure()
        num_sensors = len(serial_data_graph["temperatures"][0])  # Assuming all rows have the same number of sensors
        for i in range(num_sensors):
            figure.add_trace(
                go.Scatter(
                    x=[row / 1000 for row in serial_data_graph["delta_times"]],
                    y=[row[i] for row in serial_data_graph["temperatures"]],
                    mode='lines+markers',
                    name=f"Temperature {i + 1}"
                )
            )
            figure.update_layout(
                yaxis=dict(range=[15, 60])  # Set fixed range from 15 to 60
            )

        temps = ",  ".join([str(temp) for temp in serial_data["temperatures"][-1]])
        figure.update_layout(
            title={
                "text": "Temperatures:     " + temps,
                "font": {"size": 40},  # Adjust title font size here
            },
            xaxis_title="Delta Time (s)",
            yaxis_title="Temperature (°C)",
            legend_title="Sensors"
        )

        # Prepare table
        data = []
        for idx, time, temps in zip(serial_data["indices"], serial_data["timestamps"], serial_data["temperatures"]):
            row = {"Index": idx}
            row["Time"] = format_microseconds_to_human(time)
            for i, temp in enumerate(temps):
                row[f"Temperature {i + 1}"] = temp
            data.append(row)

        data.reverse()

        columns = [{"name": col, "id": col} for col in data[0].keys()]

        return figure, data, columns, f"Saved at: {log_path}", description


n_clicks_save_old = 0
@app.callback(
    [Input('save-button', 'n_clicks')],
    [State('text-input', 'value')]
)
def save_text_to_file(n_clicks, text):

    global log_path
    
    if n_clicks > 0 and text:
        info_file_path = f"{log_path}.info"
        try:
            with open(info_file_path, 'w') as file:
                file.write(text)
        except Exception as e:
            raise dash.exceptions.PreventUpdate(f"Error saving to {info_file_path}: {e}")
    raise dash.exceptions.PreventUpdate()



if __name__ == '__main__':
    app.run_server(debug=False)
