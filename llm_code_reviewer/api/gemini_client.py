import google.generativeai as genai
import json
from .. import config

class GeminiClient:
    # All methods below are now correctly indented inside the class
    def __init__(self):
        genai.configure(api_key=config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    def get_summary_from_diff(self, diff_content):
        """Gera um resumo de um diff."""
        prompt = (
            "Você é um assistente de IA focado em análise de código. Sua tarefa é fornecer um resumo claro e conciso das alterações em um Pull Request com base no seguinte diff. O resumo deve focar em:\n"
            "1. **O que foi mudado**: Resumo das principais alterações.\n"
            "2. **Por que foi mudado**: A intenção por trás da mudança.\n\n"
            "A resposta deve ser um parágrafo único.\n\n"
            f"```diff\n{diff_content}\n```"
        )
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Erro ao chamar a API do Gemini para resumo: {e}")
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
        """
        
        try:
            response = self.model.generate_content(prompt)
            text_to_parse = response.text.strip().removeprefix('```json\n').removesuffix('\n```')
            if text_to_parse:
                return json.loads(text_to_parse)
        except Exception as e:
            print(f"Erro ao chamar a API do Gemini para inferir tecnologia: {e}")

        return {"linguagem": "desconhecido", "arquivo_dependencias": "desconhecido"}

    def detect_code_smell(self, diff_content):
        """
        Analisa um diff para detectar a presença de qualquer code smell.
        Retorna uma resposta estruturada indicando se um problema foi encontrado.
        """
        prompt = (
            "Você é um especialista em qualidade de código. Analise o diff de código a seguir e identifique "
            "se ele possui algum 'code smell' (padrões de código problemáticos que indicam fraquezas no design).\n\n"
            "Responda estritamente com um objeto JSON contendo duas chaves:\n"
            '1. "has_code_smell": um booleano (true se encontrar algum code smell, false caso contrário).\n'
            '2. "justification": uma justificativa curta (uma única frase) para sua decisão.\n\n'
            f"```diff\n{diff_content}\n```"
        )
        try:
            response = self.model.generate_content(prompt)
            # Limpa a resposta para garantir que seja um JSON válido
            text_to_parse = response.text.strip().removeprefix('```json\n').removesuffix('\n```')
            if text_to_parse:
                return json.loads(text_to_parse)
        except Exception as e:
            print(f"Erro ao chamar a API do Gemini para detectar code smell: {e}") 

        # Retorno padrão em caso de erro
        return {"has_code_smell": False, "justification": "Não foi possível analisar o código devido a um erro."}

    def list_specific_code_smells(self, diff_content):
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
            f"```diff\n{diff_content}\n```"
        )
        try:
            response = self.model.generate_content(prompt)
            # Limpa a resposta para garantir que seja um JSON válido
            text_to_parse = response.text.strip().removeprefix('```json\n').removesuffix('\n```')
            if text_to_parse:
                return json.loads(text_to_parse)
        except Exception as e:
            print(f"Erro ao chamar a API do Gemini para listar code smells específicos: {e}") 
        
        # Retorno padrão em caso de erro
        return []        