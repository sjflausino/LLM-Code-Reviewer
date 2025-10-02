# LLM-Code-Reviewer

Este é um projeto de automação que utiliza o GitHub Actions e a API do Google Gemini para coletar, analisar e resumir Pull Requests de múltiplos repositórios. O objetivo é automatizar a etapa inicial de análise de código, fornecendo resumos concisos e orientados por IA sobre as alterações, facilitando o trabalho de revisores humanos.

## 🚀 Como Funciona

O projeto é construído como um pipeline de duas etapas no GitHub Actions, garantindo modularidade e eficiência.

1.  **Coleta e Organização dos Dados**:

      * Lê uma lista de repositórios do arquivo `repositorios.json`.
      * Usa a API do GitHub para coletar os Pull Requests mais recentes de cada repositório.
      * Extrai os "diffs" (as alterações de código) de cada Pull Request e os salva em arquivos separados na pasta `diffs/`.
      * Cria um arquivo JSON simplificado (`pr_info_simplificado.json`) com os metadados essenciais.

2.  **Geração de Resumos com IA**:

      * Utiliza a API do **Google Gemini** para gerar um resumo de alto nível para cada `diff`.
      * Injeta o resumo de IA no arquivo JSON simplificado.
      * Salva o arquivo final (`pr_info_simplificado_com_resumo.json`) como um artefato do workflow.

## 🛠️ Requisitos

Para rodar este projeto, você precisará de:

  * **GitHub Token**: Um Token de Acesso Pessoal com permissões de repositório (`repo` scope) para acessar a API do GitHub.
  * **Gemini API Key**: Uma chave de API para a API do Google Gemini. A versão gratuita é suficiente para este projeto.
  * **`repositorios.json`**: Um arquivo JSON contendo a lista de repositórios que você deseja analisar. O formato deve ser:
    ```json
    [
      {
        "owner": "dono_do_repo",
        "repo": "nome_do_repo"
      }
    ]
    ```

## ⚙️ Configuração

1.  **Chaves Secretas**: Adicione suas chaves de API como segredos no seu repositório do GitHub em **`Settings` \> `Secrets and variables` \> `Actions`**.

      * `GITHUB_TOKEN`
      * `GEMINI_API_KEY`

2.  **Workflow do GitHub Actions**: O pipeline completo está definido no arquivo `.github/workflows/analise.yml`. Ele pode ser executado manualmente, o que é ideal para este tipo de análise sob demanda.

3.  **Dependências**: Certifique-se de que as dependências do Python estejam listadas no arquivo `requirements.txt`:

      * `requests`
      * `google-generativeai`

## 🏃 Como Usar

Para executar o pipeline, vá até a aba **`Actions`** do seu repositório no GitHub, selecione o workflow **"Análise de Pull Requests em Múltiplos Repos (Python)"** e clique em **`Run workflow`**. Você pode definir o número de Pull Requests a serem analisados por repositório.

Após a execução, o arquivo final (`pr_info_simplificado_com_resumo.json`) estará disponível como um artefato para download, contendo todos os dados e os resumos gerados pela IA.

## 🤝 Contribuições

Sinta-se à vontade para contribuir\! Seja corrigindo um bug, melhorando a documentação, ou adicionando novas funcionalidades.