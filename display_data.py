import dash_bootstrap_components as dbc
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import os

# Dash app setup
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Folder containing log files
LOG_FOLDER = './logs'

def load_log_files():
    """Read the logs folder and load all CSV files into a list."""
    if not os.path.exists(LOG_FOLDER):
        return []
    return [f for f in os.listdir(LOG_FOLDER) if f.endswith('.log')]

def read_log_file(file_name):
    """Read the content of the selected log file into a DataFrame."""
    print("Loading logs from file:", file_name)
    file_path = os.path.join(LOG_FOLDER, file_name)
    try:
        return pd.read_csv(file_path, sep=';', parse_dates=['timestamp'])
    except Exception as e:
        print(f"Unable to parse '{file_name}'", e)
        return None

def read_description_file(file_name):
    """Read the description file for the corresponding log file."""
    file_path = os.path.join(LOG_FOLDER, file_name)
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return file.read().strip()
    return ""

# Load initial file list
print("Loading files ...")
log_files = load_log_files()
dfs = {log_file: read_log_file(log_file) for log_file in log_files}
dfs = {log_file: df for log_file, df in dfs.items() if df is not None} # remove all the files you cant load (None)
log_files = [log_file for log_file in log_files if log_file in dfs]
for k, v in dfs.items():
    print(k, len(v))

# Load descriptions for log files
descriptions = {log_file: read_description_file(log_file + ".info") for log_file in log_files}

print("Loading done!")



# App layout
app.layout = html.Div([
    html.H1("Temperature Log Viewer", style={'textAlign': 'center'}),
    html.Div([
        html.Label("Select a log file:"),
        dcc.Dropdown(
            id='file-dropdown',
            options=[{'label': f"{file} ({len(dfs[file])}) {descriptions[file][:20] if file in descriptions else ""}", 'value': file} for file in log_files],
            placeholder='Select a log file',
            style={'width': '50%'}
        )
    ], style={'margin': '20px'}),
    html.Div(id='file-description', style={'margin': '20px', 'fontStyle': 'italic'}),
    dcc.Graph(id='temperature-graph', style={'height': '70vh'}),
])

@app.callback(
    [Output('temperature-graph', 'figure'), Output('file-description', 'children')],
    Input('file-dropdown', 'value')
)
def update_graph(selected_file):
    """Update the graph and description based on the selected file."""
    if not selected_file:
        return {
            'data': [],
            'layout': {
                'title': 'No file selected',
                'xaxis': {'title': 'Time'},
                'yaxis': {'title': 'Temperature (°C)'}
            }
        }, "Select a file to view its description."

    try:
        df = dfs[selected_file]
        figure = {
            'data': [
                {
                    'x': df['timestamp'],
                    'y': df[col],
                    'type': 'line',
                    'name': col
                } for col in df.columns if col.startswith('temp')
            ],
            'layout': {
                'title': f'Temperature Data: {selected_file}',
                'xaxis': {'title': 'Time'},
                'yaxis': {'title': 'Temperature (°C)'}
            }
        }
        description = descriptions.get(selected_file, "No description available.")
        return figure, description
    except Exception as e:
        return {
            'data': [],
            'layout': {
                'title': f'Error reading file: {e}',
                'xaxis': {'title': 'Time'},
                'yaxis': {'title': 'Temperature (°C)'}
            }
        }, "Error loading description."

if __name__ == '__main__':
    app.run_server(debug=True)
