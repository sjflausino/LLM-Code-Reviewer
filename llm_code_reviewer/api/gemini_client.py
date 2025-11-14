import time
import google.generativeai as genai
from google.api_core import exceptions
import json
import re
from .. import config  # <-- [CORREÇÃO 1]: Importa o módulo 'config' inteiro

# Limite de caracteres para o diff (evita estouro de cota)
DIFF_TRUNCATE_LIMIT = 20000  

class GeminiClient:
    def __init__(self):
        # 'config' agora está definido e 'GEMINI_API_KEY' existe no config.py
        genai.configure(api_key=config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.5-flash') 
        
        self.total_api_calls = 0
        self.total_tokens = 0

    def _update_usage(self, response):
        """Método auxiliar para contabilizar chamadas e tokens."""
        self.total_api_calls += 1
        try:
            # Tenta acessar os metadados de uso da resposta
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                self.total_tokens += response.usage_metadata.total_token_count
        except Exception as e:
            # Não quebra a execução se a contagem falhar
            print(f"Aviso: Não foi possível contabilizar o uso de tokens. Erro: {e}")

    def get_total_calls(self):
        """Retorna o total de chamadas de API feitas."""
        return self.total_api_calls

    def get_total_tokens(self):
        """Retorna o total de tokens consumidos."""
        return self.total_tokens

    def get_summary_from_diff(self, diff_content):
        """Gera um resumo de um diff."""
        
        # Trunca o diff para evitar estouro de cota (boa prática)
        truncated_diff = diff_content[:DIFF_TRUNCATE_LIMIT]

        prompt = (
            "Você é um assistente de IA focado em análise de código. Sua tarefa é fornecer um resumo claro e conciso das alterações em um Pull Request com base no seguinte diff. O resumo deve focar em:\n"
            "1. **O que foi mudado**: Resumo das principais alterações.\n"
            "2. **Por que foi mudado**: A intenção por trás da mudança.\n\n"
            "A resposta deve ser um parágrafo único.\n\n"
            f"```diff\n{truncated_diff}\n```" # Usa diff truncado
        )
        try:
            response = self.model.generate_content(prompt)
            self._update_usage(response)
            return response.text
        except Exception as e:
            print(f"Erro ao gerar resumo: {e}")
            return "Resumo não disponível devido a um erro."

    def infer_tech_from_files(self, file_paths):
        """Usa o Gemini para inferir a linguagem e o arquivo de dependências a partir de uma lista de arquivos."""
        file_list_truncated = file_paths[:200]
        
        prompt = f"""
        Com base na seguinte lista de caminhos de arquivos de um projeto:
        {json.dumps(file_list_truncated, indent=2)}

        Identifique a linguagem de programação principal do projeto e o nome do arquivo de gerenciamento de dependências.
        Sua resposta deve ser estritamente um objeto JSON com duas chaves:
        1. "linguagem": A linguagem principal (ex: "Python", "Java", "JavaScript").
        2. "arquivo_dependencias": O nome do arquivo de dependências (ex: "requirements.txt", "package.json", "pom.xml").
        Se não conseguir identificar, retorne: {{"linguagem": "desconhecido", "arquivo_dependencias": "desconhecido"}}
        "Responda apenas com o JSON, sem texto explicativo, sem Markdown e sem comentários."
        """
        
        try:
            response = self.model.generate_content(prompt)
            self._update_usage(response) 
            text_to_parse = response.text.strip().removeprefix('```json\n').removesuffix('\n```')
            
            # Verifica se a string não está vazia
            if text_to_parse:
                return json.loads(text_to_parse)
        except Exception as e:
            print(f"Erro ao inferir tecnologia: {e}, {response.text if 'response' in locals() else 'No response'}")

        return {"linguagem": "desconhecido", "arquivo_dependencias": "desconhecido"}

    def detect_code_smell(self, diff_content):
        """
        Analisa um diff para detectar a presença de qualquer code smell.
        Retorna uma resposta estruturada indicando se um problema foi encontrado.
        """
        
        # Trunca o diff
        truncated_diff = diff_content[:DIFF_TRUNCATE_LIMIT]
        
        prompt = (
            "Você é um especialista em qualidade de código. Analise o diff de código a seguir e identifique "
            "se ele possui algum 'code smell' (padrões de código problemáticos que indicam fraquezas no design).\n\n"
            "Responda estritamente com um objeto JSON contendo duas chaves:\n"
            '1. "has_code_smell": um booleano (true se encontrar algum code smell, false caso contrário).\n'
            '2. "justification": uma justificativa curta (uma única frase) para sua decisão.\n\n'
            f"```diff\n{truncated_diff}\n```" # Usa diff truncado
        )
        try:
            response = self.model.generate_content(prompt)
            self._update_usage(response)
            text_to_parse = response.text.strip().removeprefix('```json\n').removesuffix('\n```')
            if text_to_parse:
                return json.loads(text_to_parse)
        except Exception as e:
            print(f"Erro ao detectar code smell: {e}") 

        return {"has_code_smell": False, "justification": "Não foi possível analisar o código devido a um erro."}

    def list_specific_code_smells(self, diff_content):
            """
            Dado um diff que contém code smells, lista e descreve cada um deles.
            """
            
            # Trunca o diff para evitar estouro de cota
            truncated_diff = diff_content[:DIFF_TRUNCATE_LIMIT]
            if len(diff_content) > DIFF_TRUNCATE_LIMIT:
                print(f"  Aviso: Diff truncado para {DIFF_TRUNCATE_LIMIT} caracteres (limite de cota).")

            prompt = (
                "O diff de código a seguir foi previamente identificado como contendo 'code smells'. "
                "Sua tarefa é listar e descrever cada problema encontrado.\n\n"
                "Para cada code smell, forneça:\n"
                "- O nome do code smell (ex: 'Long Method', 'Magic Number', 'N+1 Query').\n"
                "- Uma descrição concisa do problema no contexto do código apresentado.\n"
                "- Uma sugestão de como refatorar o código para corrigir o problema.\n\n"
                "Formate sua resposta como uma lista de objetos JSON, com as chaves 'smell_type', 'description' e 'suggestion'.\n" 
                "Se, após uma análise detalhada, você não encontrar NENHUM code smell (apesar da indicação anterior), "
                "retorne uma lista vazia [].\n\n"
                f"```diff\n{truncated_diff}\n```" # Usa o diff truncado
            )
            
            raw_text = "" 
            try:
                response = self.model.generate_content(prompt) 
                self._update_usage(response)
                raw_text = response.text.strip()
                
                found_smells = []
                
                # Regex para encontrar todos os objetos JSON (não-guloso)
                # re.DOTALL faz o '.' incluir quebras de linha
                object_matches = re.finditer(r'(\{.*?\})', raw_text, re.DOTALL)
                
                for match in object_matches:
                    potential_json_object = match.group(1)
                    try:
                        # Tenta decodificar o objeto individualmente
                        smell_object = json.loads(potential_json_object)
                        
                        # Verificação de sanidade: o objeto tem o que esperamos?
                        if 'smell_type' in smell_object and 'description' in smell_object:
                            found_smells.append(smell_object)
                        else:
                            # Encontrou um JSON, mas não era um code smell
                            print(f"Aviso: Objeto JSON ignorado (faltando chaves): {potential_json_object[:50]}...")
                            
                    except json.JSONDecodeError:
                        # Se falhar, é lixo ou JSON quebrado (como no log). Ignora e continua.
                        continue 

                # Se não encontramos nada, mas a resposta não estava vazia, loga.
                if not found_smells and raw_text and not raw_text.startswith('[]'):
                    print(f"Aviso: A API do Gemini não retornou objetos JSON válidos para list_specific_code_smells.")
                    print(f"--- Resposta Bruta (Sem Objetos) ---")
                    print(raw_text)
                    print(f"----------------------------------")

                return found_smells

            except Exception as e:
                # Erros gerais (ex: falha na chamada da API)
                print(f"Erro (Geral) ao chamar a API do Gemini para listar code smells específicos: {e}") 
                if raw_text:
                    print(f"--- Resposta Bruta (Erro Geral) ---")
                    print(raw_text)
                    print(f"-----------------------------------")
                return []
