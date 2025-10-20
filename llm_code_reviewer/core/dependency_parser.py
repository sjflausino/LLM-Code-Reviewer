import json
import re

def _parse_requirements_txt(file_content):
    """Extrai pacotes e versões exatas de um requirements.txt."""
    packages = []
    # Regex para encontrar pacotes com versão exata (ex: requests==2.28.1)
    # Ignora comentários e linhas vazias
    req_pattern = re.compile(r"^\s*([\w\d\-_]+)\s*==\s*([\w\d\._\-]+)", re.MULTILINE)
    
    for match in req_pattern.finditer(file_content):
        packages.append({
            "name": match.group(1),
            "version": match.group(2),
            "ecosystem": "PyPI"
        })
    return packages

def _parse_package_json(file_content):
    """Extrai pacotes e versões de um package.json."""
    packages = []
    try:
        data = json.loads(file_content)
        
        # Regex para limpar prefixos de versão como ^, ~, >=
        version_cleaner = re.compile(r"^[^\d]*")
        
        # Agrega dependências de produção e desenvolvimento
        dependencies = {
            **(data.get("dependencies", {})),
            **(data.get("devDependencies", {}))
        }
        
        for name, version_str in dependencies.items():
            # Limpa a string de versão para obter apenas o número
            # Ex: "^1.2.3" -> "1.2.3"
            clean_version = version_cleaner.sub("", version_str)
            if clean_version:
                packages.append({
                    "name": name,
                    "version": clean_version,
                    "ecosystem": "npm"
                })
    except json.JSONDecodeError:
        print("Erro: Falha ao decodificar o package.json.")
    
    return packages

def parse(file_content, ecosystem):
    """Função principal que roteia para o parser correto."""
    if ecosystem == "PyPI":
        return _parse_requirements_txt(file_content)
    elif ecosystem == "npm":
        return _parse_package_json(file_content)
    
    print(f"Aviso: Nenhum parser implementado para o ecossistema '{ecosystem}'.")
    return []