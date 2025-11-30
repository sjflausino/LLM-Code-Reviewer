import time
import google.generativeai as genai
from google.api_core import exceptions
import json
import re
from .. import config

PROMPT_LIMIT = 250000

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

    def list_commit_code_smells(self, diff_content):
        """
        Dado um diff que contém code smells, lista e descreve cada um deles.
        """
        prompt = (
            "O diff de código a seguir foi previamente identificado como contendo 'code smells'. "
            "Sua tarefa é listar e descrever cada problema encontrado.\n\n"
            "Para cada code smell, forneça:\n"
            "- O nome do code smell (ex: 'Long Method', 'Magic Number', 'N+1 Query').\n"
            "- Uma descrição concisa do problema no contexto do código apresentado.\n"
            "- Uma sugestão de como refatorar o código para corrigir o problema.\n\n"
            "Formate sua resposta como uma lista de objetos JSON, com as chaves 'smell_type', 'description' e 'suggestion'.\n\n"
            "Responda apenas com o JSON, sem texto explicativo, sem Markdown e sem comentários."
            f"```diff\n{diff_content}\n```"
        )
        try:
            response = self.call_gemini_api(prompt)
            text_to_parse = response.text.strip().removeprefix('```json\n').removesuffix('\n```')
            if text_to_parse:
                return json.loads(text_to_parse)
        except Exception as e:
            print(f"Erro ao listar code smell específicos: {e}")
        
        return []
    
    def analyze_pr_diff(self, diff_content):
        """
        Combina Resumo e Análise de Code Smells em um único prompt para economizar requisições.
        """
        prompt = (
            "Você é um especialista em Code Review (Tech Lead). Analise o diff de código abaixo.\n"
            "Sua saída deve ser ESTRITAMENTE um objeto JSON contendo duas chaves: 'summary' e 'code_smells'.\n\n"
            
            "1. 'summary' (string): Um parágrafo único, claro e conciso explicando:\n"
            "   - O que mudou (alterações principais).\n"
            "   - Por que mudou (intenção inferida).\n\n"
            
            "2. 'code_smells' (lista de objetos): Identifique problemas de qualidade ou vulnerabilidades no código (se houver).\n"
            "   Para cada item, inclua:\n"
            "   - 'smell_type': Nome do padrão (ex: Long Method, Magic Number).\n"
            "   - 'description': Breve descrição contextualizada.\n"
            "   - 'suggestion': Como refatorar.\n\n"
            
            "Se não houver code smells ou vulnerabilidades, retorne uma lista vazia.\n"
            "Responda apenas com o JSON, sem texto explicativo, sem Markdown e sem comentários."
            f"DIFF DO CÓDIGO:\n```diff\n{diff_content}\n```"
        )

        try:
            response = self.call_gemini_api(prompt)
            text_to_parse = response.text.strip().removeprefix('```json\n').removesuffix('\n```')

            
            data = json.loads(text_to_parse)
            
            return {
                "summary": data.get("summary", "Resumo indisponível."),
                "code_smells": data.get("code_smells", [])
            }
        except Exception as e:
            print(f"Erro na análise do PR: {e}")

            return {
                "summary": "Erro ao gerar análise.",
                "code_smells": []
            }
    
    def call_gemini_api(self, prompt, retry_count=0, max_retries=3):
        """Chamada genérica à API do Gemini com contabilização de uso."""
        # if(self.client.models.count_tokens(model=''gemini-2.5-flash'', contents=[prompt]) > 0):
        try:
            prompt_tokens = self.model.count_tokens(contents=[prompt]).total_tokens
            if prompt_tokens > PROMPT_LIMIT:
                print(f"Aviso: O prompt excede o limite de {PROMPT_LIMIT} tokens. Truncando.")
                raise ValueError("Prompt muito grande para a API gratuita do Gemini.")
            start = time.time()
            response = self.model.generate_content(prompt)
            self._update_usage(response)
            end = time.time()
            print(f"Tempo de resposta da API Gemini: {end - start:.2f} segundos")
            return response
        except exceptions.GoogleAPICallError as e:
            status = getattr(e, "code", None)
            message = str(e)

            if status == 429 or "quota" in message.lower():

                print(f"⚠️ Erro 429: Limite de quota atingido. Tentativa {retry_count + 1} de {max_retries}.")

                # Tenta detectar o tipo de quota no corpo da mensagem
                if "GenerateRequestsPerDayPerProjectPerModel" in message:
                    # 🚫 Limite diário -> interrompe a aplicação
                    print("\n🚨 Limite diário de requisições atingido.")
                    raise
                
                # ⏳ Caso seja outra quota (por minuto ou burst)
                elif retry_count < max_retries:
                    print("🔁 Limite temporário atingido. Tentando novamente em 60s...")
                    time.sleep(60)
                    return self.call_gemini_api(prompt, retry_count + 1, max_retries)
                else:
                    print("❌ Número máximo de tentativas atingido. Abortando.")
                    raise

            # Outros erros da API
            print(f"Erro ao chamar API do Gemini: {e}")
            raise
