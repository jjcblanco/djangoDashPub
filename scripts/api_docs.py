# api_docs.py
import os
import re
from pathlib import Path

class APIDocumentationGenerator:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.endpoints = []
        self.serializers = []
        self.views = []
    
    def find_django_apps(self):
        """Encuentra todas las aplicaciones Django en el proyecto"""
        apps = []
        for item in self.project_root.iterdir():
            if item.is_dir() and (item / 'apps.py').exists():
                apps.append(item.name)
        return apps
    
    def extract_url_patterns(self, urls_content):
        """Extrae patrones de URL del contenido de urls.py"""
        patterns = []
        
        # Buscar patrones de path() y url()
        path_patterns = re.findall(r'path\([\s\S]*?\)', urls_content)
        url_patterns = re.findall(r'url\([\s\S]*?\)', urls_content)
        
        all_patterns = path_patterns + url_patterns
        
        for pattern in all_patterns:
            # Extraer la ruta y la vista
            route_match = re.search(r"['\"]([^'\"]+)['\"]", pattern)
            view_match = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*\.)*([a-zA-Z_][a-zA-Z0-9_]*)', pattern)
            
            if route_match and view_match:
                endpoint = {
                    'route': route_match.group(1),
                    'view': view_match.group(0)
                }
                
                # Intentar extraer el nombre
                name_match = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", pattern)
                if name_match:
                    endpoint['name'] = name_match.group(1)
                
                patterns.append(endpoint)
        
        return patterns
    
    def extract_view_info(self, view_content, view_name):
        """Extrae información de una vista"""
        view_info = {
            'name': view_name,
            'methods': [],
            'docstring': ''
        }
        
        # Buscar docstring
        docstring_match = re.search(r'\"\"\"([\s\S]*?)\"\"\"|\'\'\'([\s\S]*?)\'\'\'', view_content)
        if docstring_match:
            view_info['docstring'] = docstring_match.group(1) or docstring_match.group(2) or ''
        
        # Buscar métodos HTTP
        http_methods = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
        for method in http_methods:
            if re.search(rf'def {method}\(', view_content, re.IGNORECASE):
                view_info['methods'].append(method.upper())
        
        return view_info
    
    def generate_markdown_docs(self):
        """Genera documentación en formato Markdown"""
        docs = "# Documentación de la API\n\n"
        
        # Endpoints
        docs += "## Endpoints\n\n"
        for endpoint in self.endpoints:
            docs += f"### {endpoint.get('name', endpoint['route'])}\n"
            docs += f"- **Ruta**: `{endpoint['route']}`\n"
            docs += f"- **Vista**: `{endpoint['view']}`\n"
            
            if 'methods' in endpoint:
                docs += f"- **Métodos**: {', '.join(endpoint['methods'])}\n"
            
            if 'docstring' in endpoint and endpoint['docstring']:
                docs += f"- **Descripción**: {endpoint['docstring']}\n"
            
            docs += "\n"
        
        return docs
    
    def analyze_project(self):
        """Analiza todo el proyecto"""
        apps = self.find_django_apps()
        
        for app in apps:
            app_path = self.project_root / app
            
            # Buscar urls.py
            urls_file = app_path / 'urls.py'
            if urls_file.exists():
                with open(urls_file, 'r', encoding='utf-8') as f:
                    urls_content = f.read()
                
                endpoints = self.extract_url_patterns(urls_content)
                self.endpoints.extend(endpoints)
            
            # Buscar views.py
            views_file = app_path / 'views.py'
            if views_file.exists():
                with open(views_file, 'r', encoding='utf-8') as f:
                    views_content = f.read()
                
                # Buscar clases de vistas
                class_matches = re.findall(r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)', views_content)
                for class_name in class_matches:
                    # Extraer contenido de la clase
                    class_pattern = rf'class\s+{class_name}[\s\S]*?(?=class|\Z)'
                    class_match = re.search(class_pattern, views_content)
                    
                    if class_match:
                        view_info = self.extract_view_info(class_match.group(0), class_name)
                        self.views.append(view_info)
        
        # Asociar vistas con endpoints
        for endpoint in self.endpoints:
            view_name = endpoint['view'].split('.')[-1]
            for view in self.views:
                if view['name'] == view_name:
                    endpoint.update(view)
                    break

# Uso del generador de documentación
if __name__ == "__main__":
    project_path = "."
    doc_generator = APIDocumentationGenerator(project_path)
    doc_generator.analyze_project()
    
    # Generar documentación Markdown
    markdown_docs = doc_generator.generate_markdown_docs()
    
    with open('API_DOCUMENTATION.md', 'w', encoding='utf-8') as f:
        f.write(markdown_docs)
    
    print("Documentación generada: API_DOCUMENTATION.md")
    
    # También generar JSON para fácil procesamiento
    import json
    with open('api_endpoints.json', 'w', encoding='utf-8') as f:
        json.dump({
            'endpoints': doc_generator.endpoints,
            'views': doc_generator.views
        }, f, indent=2, ensure_ascii=False)