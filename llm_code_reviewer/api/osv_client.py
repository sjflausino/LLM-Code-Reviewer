import requests
import json

# Documentação da API: https://osv.dev/docs/#tag/api
OSV_API_URL = "https://api.osv.dev/v1/querybatch"

class OsvClient:
    def __init__(self):
        self.session = requests.Session()

    def _create_package_query(self, package):
        """Cria a estrutura de query para um único pacote."""
        # A API do OSV funciona melhor com versões exatas.
        # O parser (Passo 2) tentará extrair versões exatas.
        return {
            "version": package.get("version"),
            "package": {
                "name": package.get("name"),
                "ecosystem": package.get("ecosystem")
            }
        }

    def check_vulnerabilities(self, packages_list):
        """
        Verifica uma lista de pacotes contra o banco de dados OSV.
        
        packages_list deve ser uma lista de dicts:
        [
            {"name": "requests", "version": "2.18.0", "ecosystem": "PyPI"},
            {"name": "express", "version": "4.17.0", "ecosystem": "npm"}
        ]
        """
        if not packages_list:
            return []

        # Monta a query em lote
        queries = [self._create_package_query(pkg) for pkg in packages_list]
        request_data = {"queries": queries}

        try:
            response = self.session.post(OSV_API_URL, data=json.dumps(request_data))
            response.raise_for_status() # Lança erro para respostas 4xx/5xx
            
            results = response.json().get("results", [])
            found_vulnerabilities = []

            # Processa os resultados
            for i, res in enumerate(results):
                if res and res.get("vulns"):
                    pkg = packages_list[i]
                    for vuln in res.get("vulns"):
                        found_vulnerabilities.append({
                            "package_name": pkg["name"],
                            "package_version": pkg["version"],
                            "vulnerability_id": vuln.get("id"),
                            "summary": vuln.get("summary", "Sem resumo disponível."),
                            "url": f"https://osv.dev/vulnerability/{vuln.get('id')}"
                        })
            
            return found_vulnerabilities

        except requests.exceptions.RequestException as e:
            print(f"Erro ao chamar a API do OSV: {e}")
            return []
        except json.JSONDecodeError:
            print("Erro ao decodificar a resposta JSON do OSV.")
            return []