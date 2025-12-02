# analyzer.py
import ast
import os
from pathlib import Path
import networkx as nx
import matplotlib.pyplot as plt
import json

class DjangoCodeAnalyzer:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.functions = {}
        self.call_graph = nx.DiGraph()
        
    def extract_python_files(self):
        """Extrae todos los archivos Python del proyecto"""
        python_files = []
        for root, dirs, files in os.walk(self.project_root):
            # Excluir entornos virtuales y directorios de migración
            if 'venv' in root or 'migrations' in root or '__pycache__' in root:
                continue
            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)
        return python_files
    
    def extract_function_info(self, file_path):
        """Extrae información de funciones de un archivo Python"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
            functions = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_info = {
                        'name': node.name,
                        'file': str(file_path.relative_to(self.project_root)),
                        'lineno': node.lineno,
                        'calls': [],
                        'docstring': ast.get_docstring(node) or ''
                    }
                    
                    # Encontrar llamadas dentro de la función
                    for subnode in ast.walk(node):
                        if isinstance(subnode, ast.Call):
                            if isinstance(subnode.func, ast.Name):
                                func_info['calls'].append(subnode.func.id)
                    
                    functions.append(func_info)
            
            return functions
        except SyntaxError:
            return []
    
    def analyze_project(self):
        """Analiza todo el proyecto"""
        python_files = self.extract_python_files()
        
        for file_path in python_files:
            functions = self.extract_function_info(file_path)
            for func in functions:
                func_id = f"{func['file']}::{func['name']}"
                self.functions[func_id] = func
                self.call_graph.add_node(func_id, **func)
                
                # Agregar aristas para las llamadas
                for called_func in func['calls']:
                    # Buscar la función llamada en otras funciones
                    for target_func_id, target_func in self.functions.items():
                        if target_func['name'] == called_func:
                            self.call_graph.add_edge(func_id, target_func_id)
    
    def generate_dependency_graph(self, output_file='dependencies.html'):
        """Genera un gráfico interactivo de dependencias"""
        import plotly.graph_objects as go
        
        # Posicionar nodos
        pos = nx.spring_layout(self.call_graph, k=1, iterations=50)
        
        edge_x = []
        edge_y = []
        for edge in self.call_graph.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        
        node_x = []
        node_y = []
        node_text = []
        for node in self.call_graph.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            func_info = self.functions[node]
            node_text.append(f"{func_info['name']}<br>{func_info['file']}")
        
        fig = go.Figure()
        
        # Agregar aristas
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=0.5, color='#888'),
            hoverinfo='none',
            mode='lines'
        ))
        
        # Agregar nodos
        fig.add_trace(go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            text=[node.split('::')[-1] for node in self.call_graph.nodes()],
            textposition="top center",
            hovertext=node_text,
            hoverinfo='text',
            marker=dict(
                size=20,
                color='lightblue',
                line_width=2
            )
        ))
        
        fig.update_layout(
            title='Gráfico de Dependencias de Funciones',
            titlefont_size=16,
            showlegend=False,
            hovermode='closest',
            margin=dict(b=20,l=5,r=5,t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
        )
        
        fig.write_html(output_file)
        return output_file
    
    def generate_api_documentation(self):
        """Genera documentación de la API"""
        api_docs = {
            'endpoints': [],
            'models': [],
            'views': []
        }
        
        # Buscar archivos de vistas y URLs
        for root, dirs, files in os.walk(self.project_root):
            for file in files:
                if file in ['urls.py', 'views.py']:
                    file_path = Path(root) / file
                    self._extract_api_info(file_path, api_docs)
        
        return api_docs
    
    def _extract_api_info(self, file_path, api_docs):
        """Extrae información de la API de un archivo"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                # Buscar patrones de Django
                if isinstance(node, ast.ClassDef):
                    if any(base.id == 'APIView' for base in node.bases if isinstance(base, ast.Name)):
                        api_docs['views'].append({
                            'name': node.name,
                            'file': str(file_path.relative_to(self.project_root))
                        })
        
        except SyntaxError:
            pass

# Uso del analizador
if __name__ == "__main__":
    project_path = "."
    analyzer = DjangoCodeAnalyzer(project_path)
    analyzer.analyze_project()
    
    # Generar gráfico de dependencias
    output_file = analyzer.generate_dependency_graph()
    print(f"Gráfico generado: {output_file}")
    
    # Generar documentación de API
    api_docs = analyzer.generate_api_documentation()
    
    # Guardar documentación
    with open('api_documentation.json', 'w', encoding='utf-8') as f:
        json.dump(api_docs, f, indent=2, ensure_ascii=False)
    
    print("Documentación de API generada: api_documentation.json")