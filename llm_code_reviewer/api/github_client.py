import requests
from .. import config
import base64

class GitHubClient:
    def __init__(self):
        self.token = config.GITHUB_TOKEN
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.token}"
        }

    def get_pull_requests(self, owner, repo, pull_requests_list=[]):

        if pull_requests_list:
            """Retorna uma lista específica de pull requests."""
            prs = []
            for pr_number in pull_requests_list:
                url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
                try:
                    response = requests.get(url, headers=self.headers)
                    response.raise_for_status()
                    prs.append(response.json())
                except requests.exceptions.RequestException as e:
                    print(f"Erro ao buscar o PR #{pr_number} de {owner}/{repo}: {e}")
            return prs
        
        """Busca os últimos pull requests de um repositório."""
        # All lines below this are now correctly indented
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        params = {
            "state": "all",
            "per_page": config.NUM_PULLS,
            "sort": "updated",
            "direction": "desc"
        }
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar pull requests de {owner}/{repo}: {e}")
            return None

    def get_pr_diff(self, owner, repo, pr_number):
        """Busca o diff de um pull request específico."""
        url = f"https://github.com/{owner}/{repo}/pull/{pr_number}.diff"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar o diff do PR #{pr_number} em {owner}/{repo}: {e}")
            return None

    def get_repo_structure(self, owner, repo):
        """Busca a estrutura de arquivos de um repositório (recursivamente)."""
        # All lines below this are now correctly indented
        branches_to_try = ['main', 'master', 'latest']
        for branch in branches_to_try:
            url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
            try:
                print(f"-> Buscando estrutura de arquivos no branch '{branch}'...")
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                tree = response.json().get('tree', [])
                file_paths = [item['path'] for item in tree if item['type'] == 'blob']
                return file_paths
            except requests.exceptions.RequestException as e:
                if response.status_code == 404:
                    print(f"  Branch '{branch}' não encontrado. Tentando o próximo...")
                    continue
                else:
                    print(f"Erro ao buscar a estrutura do repositório {owner}/{repo}: {e}")
                    return []
        
        print("!! Nenhum branch padrão ('main' ou 'master') encontrado.")
        return []

    def get_file_content(self, owner, repo, file_path):
            """Busca o conteúdo de um arquivo específico no repositório."""
            url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
            
            # Tenta com 'main' e 'master' se o branch não for especificado
            # A API de contents usa o branch padrão automaticamente
            
            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                if data.get("type") == "file" and data.get("encoding") == "base64":
                    content_base64 = data.get("content")
                    content_decoded = base64.b64decode(content_base64).decode("utf-8")
                    return content_decoded
                else:
                    print(f"Erro: O caminho {file_path} não é um arquivo ou não está em base64.")
                    return None
                    
            except requests.exceptions.RequestException as e:
                print(f"Erro ao buscar o conteúdo do arquivo {file_path} em {owner}/{repo}: {e}")
                return None