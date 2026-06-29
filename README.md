# ⚖️ Juri-AI

> Um sistema inteligente e eficiente para gestão de clientes e documentos jurídicos, com foco em automação e IA.

![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)
![Django](https://img.shields.io/badge/Django-5+-green?style=for-the-badge&logo=django)
![Status](https://img.shields.io/badge/Status-Em_Desenvolvimento-yellow?style=for-the-badge)

---

## 📋 Sobre o Projeto

O **Juri-AI** é uma plataforma web inteligente criada para modernizar a rotina de advogados e escritórios de advocacia.
Ela centraliza o gerenciamento de clientes e documentos jurídicos, garantindo acesso rápido, seguro e personalizado para cada profissional.

Além da gestão tradicional, o projeto integra tecnologias de Inteligência Artificial para automatizar tarefas repetitivas e análises documentais, como:

- Leitura e interpretação de documentos jurídicos (OCR).
- Conversão de arquivos para formatos padronizados (Markdown).
- Busca inteligente em documentos usando técnicas de RAG (Retrieval-Augmented Generation).
- Processamento assíncrono de tarefas pesadas, garantindo eficiência sem travar o sistema.

O Juri-AI une segurança, automação e inteligência, transformando dados jurídicos complexos em informações acessíveis e organizadas, permitindo que advogados foquem no que realmente importa: analisar casos e tomar decisões estratégicas.

---

## ✨ Funcionalidades Principais

### 🔐 Autenticação Segura
- Cadastro de usuários com validação de senha.
- Login e logout utilizando Django Auth.
- Proteção de rotas (apenas usuários autenticados).

### 👥 Gestão de Clientes
- Cadastro detalhado de clientes (Nome, E-mail, Tipo, Status).
- Listagem de clientes exclusiva por usuário (multi-tenancy).
- Visualização de dados individuais de cada cliente.

### 📂 Gestão Documental
- Upload de documentos vinculados a clientes.
- Organização por tipo de documento.
- Histórico de uploads com data e responsável.

### 🗂️ Painel de Gestão Jurídica (app `gestao`)
- **Dashboard / Indicadores:** visão geral com processos ativos, prazos a vencer, audiências próximas, tarefas abertas e resumo financeiro.
- **Processos judiciais:** cadastro completo (número CNJ, área, vara, comarca, instância, valor da causa), filtros, busca e registro de movimentações/andamentos.
- **Agenda:** linha do tempo unificada de compromissos e audiências.
- **Audiências:** agendamento e acompanhamento por status (agendada, realizada, cancelada, adiada).
- **Prazos:** controle de prazos processuais com prioridade, alerta de vencimento/atraso e marcação de cumprimento.
- **Tarefas:** quadro de rotina (a fazer / em andamento / concluídas).
- **Financeiro:** receitas, despesas, honorários, saldo, a receber e a pagar.
- **Relatórios:** processos por área e status, prazos cumpridos/perdidos e receitas por categoria.
- **Controle de acessos:** perfis de usuário por cargo (Administrador, Advogado, Estagiário, Secretária, Financeiro).

---

## 🤖 Assistente de IA (app `ia`)

Pipeline de IA que processa cada documento enviado e permite consultá-los em linguagem natural:

- 🔍 **OCR / Conversão para Markdown** via `docling` (com fallback de leitura simples).
- 🔗 **RAG (Retrieval-Augmented Generation)** — o conteúdo é dividido em trechos, vetorizado por *embeddings* e indexado no `LanceDB`.
- 💬 **Assistente Jurídico** (`/ia/assistente/`) — faça perguntas sobre os documentos; as respostas são geradas pelo **Claude (Anthropic)** com os trechos-fonte citados.
- ⏱️ **Processamento assíncrono** com `django-q` (OCR → indexação encadeados no upload).

> **Configuração da IA:**
> - **Respostas (Claude):** defina `ANTHROPIC_API_KEY` (opcional: `IA_CLAUDE_MODEL`, padrão `claude-opus-4-8`). É a **única chave obrigatória**.
> - **Embeddings (busca):** a Anthropic não oferece embeddings, então o backend é configurável via `IA_EMBEDDING_BACKEND`:
>   - `local` *(padrão)* — roda via `transformers`, **sem chave de API** (`IA_EMBEDDING_MODEL_LOCAL`, padrão `all-MiniLM-L6-v2`).
>   - `openai` — requer `OPENAI_API_KEY` (`IA_EMBEDDING_MODEL`).
>   - `voyage` — requer `VOYAGE_API_KEY` (`IA_VOYAGE_MODEL`), parceira recomendada pela Anthropic.
>
> ⚠️ Ao trocar de backend de embeddings, reindexe os documentos (apague a pasta `lancedb/`), pois as dimensões dos vetores mudam.
>
> Sem as chaves/dependências o sistema continua funcionando e o assistente exibe um aviso de configuração.

---

## 🚀 Tecnologias Utilizadas

- **Backend:** Python, Django Framework  
- **Frontend:** HTML, CSS (Django Templates)  
- **Banco de Dados:** SQLite (Desenvolvimento) / PostgreSQL (Produção)
- **IA & Processamento:** OCR, Markdown, RAG  
- **Tarefas Assíncronas:** Django-Q / Celery

---

## 💻 Pré-requisitos

Antes de iniciar, certifique-se de ter instalado:

- Python 3.12+
- Pip (gerenciador de pacotes)
- Git

---

## 🔧 Instalação e Execução

Siga os passos abaixo para rodar o projeto localmente:

### 1️⃣ Clone o repositório
```bash
git clone https://github.com/GuilhermeBeserra/JURI-AI.git
cd Juri-AI
```

### 2️⃣ Crie o ambiente virtual
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / Mac
python3 -m venv venv
source venv/bin/activate
```

### 3️⃣ Instale as dependências
```bash
pip install -r requirements.txt
```

### 4️⃣ Configure o Banco de Dados
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5️⃣ Inicie o servidor
```bash
python manage.py runserver
```

Acesse o projeto em: `http://127.0.0.1:8000/`

### 6️⃣ Rodar os testes
```bash
python manage.py test
```
A suíte cobre perfis/controle de acesso, multi-tenancy, fluxos de processos/prazos/tarefas/financeiro e a camada de IA (chunking, seleção de backend e degradação graciosa).

---

## 🚀 Deploy em produção (Docker)

O sistema já vem pronto para subir em produção com **Docker Compose** (Caddy/HTTPS + web + worker de fila + PostgreSQL). O **Caddy emite e renova o certificado HTTPS automaticamente** (Let's Encrypt) assim que o domínio apontar para o servidor.

```bash
# 1) No servidor (VPS com Docker), clone o repositório
git clone https://github.com/tiagonevesjus-png/JURI-AI.git && cd JURI-AI

# 2) Configure as variáveis de ambiente
cp .env.example .env
nano .env     # DOMAIN, SECRET_KEY, ADMIN_PASSWORD, ANTHROPIC_API_KEY, senha do banco...

# 3) Suba os serviços (build + migração + criação do admin + estáticos + HTTPS)
docker compose up -d --build

# 4) Acesse https://SEU_DOMINIO  (login com ADMIN_USERNAME / ADMIN_PASSWORD do .env)
```

### Apontar o domínio (DNS)
No painel do registrador (ex.: **Registro.br**), crie os registros apontando para o **IP do servidor**:

| Tipo | Nome | Valor |
|---|---|---|
| `A` | `@` (ou o domínio) | IP público do servidor |
| `A` | `www` | IP público do servidor |

Após a propagação do DNS, o Caddy emite o certificado sozinho no primeiro acesso. **Abra as portas 80 e 443** no firewall do servidor.

O que o start automático faz (via `docker/entrypoint.sh`):
- aplica as migrações do banco;
- cria/atualiza o usuário administrador (`manage.py setup_inicial`, a partir do `.env`);
- coleta os arquivos estáticos;
- sobe o **gunicorn** (web) e o **qcluster** (processamento assíncrono de OCR/indexação).

### Imagens: base vs. completa
- **`requirements-base.txt`** (usada no Docker): gestão completa + assistente **Claude** + RAG com embeddings da **OpenAI**. Imagem leve.
- **`requirements.txt`** (completa): adiciona **OCR de PDFs** (`docling`) e **embeddings locais** (`transformers`/`torch`). Para usar, defina `IA_EMBEDDING_BACKEND=local` e troque a base por `requirements.txt` no `Dockerfile`.

### Variáveis essenciais (`.env`)
| Variável | Para quê |
|---|---|
| `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Segurança/produção do Django |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL` | Usuário administrador inicial |
| `POSTGRES_DB/USER/PASSWORD` | Banco PostgreSQL |
| `ANTHROPIC_API_KEY` | Respostas do assistente (Claude) |
| `IA_EMBEDDING_BACKEND` + `OPENAI_API_KEY` | Busca por embeddings (`openai` na imagem base) |

> Sem `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` o sistema funciona normalmente; apenas o assistente de IA exibe um aviso de configuração.

---

## ☁️ Deploy gratuito (Render.com + backup no OneDrive)

Opção **sem custo e sem cartão**: o Render hospeda a API e o PostgreSQL, com SSL automático; os backups vão para o seu OneDrive.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/tiagonevesjus-png/JURI-AI)

> Clique no botão acima (faça login no Render com o GitHub), revise os serviços que o `render.yaml` propõe e clique **Apply**. Em seguida defina os segredos (`ADMIN_PASSWORD` e, se for usar IA, `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`).

### 1) Subir no Render
1. Garanta o repositório no GitHub (já está).
2. No **Render** → **New** → **Blueprint** → conecte o repositório → **Apply**. O `render.yaml` cria o **web service** + **PostgreSQL** automaticamente.
3. Após o 1º deploy, em **Environment**, defina os segredos: `ADMIN_PASSWORD` e, se for usar IA, `ANTHROPIC_API_KEY` e `OPENAI_API_KEY`. Faça um **Manual Deploy** para aplicar.
4. Acesse a URL `https://juriai.onrender.com` (login com `tiago` / `ADMIN_PASSWORD`).
5. **Domínio próprio:** em **Settings → Custom Domains**, adicione `tiagonevesadv.com.br` e crie no Registro.br um registro **CNAME** (`www`) apontando para o host do Render, ou siga as instruções exibidas pelo Render. O SSL é emitido automaticamente.

### 2) Backups automáticos no OneDrive
O workflow `.github/workflows/backup.yml` faz um dump diário do banco e envia ao OneDrive (roda nos GitHub Actions, de graça). Configure os **Secrets** do repositório (Settings → Secrets and variables → Actions):
- `DATABASE_URL_EXTERNAL` — a *External Database URL* do Postgres no Render.
- `RCLONE_CONFIG_BASE64` — seu `rclone.conf` (com um remote OneDrive) em base64:
  ```bash
  rclone config                                  # crie um remote chamado "onedrive"
  base64 -w0 ~/.config/rclone/rclone.conf        # cole o resultado no secret
  ```
- *(opcional)* `ONEDRIVE_REMOTE` — pasta de destino (padrão `onedrive:JuriAI-Backups`).

> **Limitações do plano gratuito do Render (importante para uso real):**
> - O serviço **hiberna** após ~15 min sem acesso (primeiro acesso seguinte demora ~50s).
> - O **PostgreSQL gratuito é removido após ~30 dias** — os backups no OneDrive são a sua rede de segurança; para uso contínuo, o banco pago do Render custa ~US$ 7/mês.
> - O **disco é efêmero**: os dados da gestão (no Postgres) persistem, mas **arquivos enviados e o índice de IA se perdem ao reiniciar**. Para mantê-los, use um disco persistente (instância paga) ou armazenamento externo.
> - Os dados ficam em datacenter fora do Brasil — avalie a questão de **LGPD** para dados sensíveis de clientes.

---

## ✅ O que falta para usar

O sistema está **funcional e pronto para deploy**. Para colocar em uso real:
1. **Servidor**: uma VM/VPS com Docker (qualquer provedor) e IP público.
2. **DNS**: apontar os registros `A` (`@` e `www`) do domínio para o IP do servidor.
3. **`.env`**: preencher `DOMAIN`, `SECRET_KEY`, `ADMIN_PASSWORD` e a senha do banco.
4. **(Opcional) IA**: definir `ANTHROPIC_API_KEY` (e `OPENAI_API_KEY` se usar embeddings na nuvem) para ligar o assistente jurídico.
5. `docker compose up -d --build` — o **HTTPS é automático** (Caddy + Let's Encrypt).

---

## ⚙️ Configuração e Boas Práticas

### 🛡️ .gitignore e Banco de Dados
Para manter o repositório limpo e seguro, certifique-se de que seu arquivo `.gitignore` inclua os seguintes itens:

```text
venv/
*.pyc
__pycache__/
db.sqlite3
.env
```

> **⚠️ Aviso Importante:** O arquivo `db.sqlite3` **não deve ser versionado**. Cada ambiente (desenvolvimento, produção) deve possuir seu próprio banco de dados, criado e atualizado através das migrações do Django.

---

## Estrutura do Projeto

```text
Juri-AI/
├── core/                # Configurações principais do projeto (settings, urls)
├── gestao/              # Painel de gestão: processos, agenda, prazos, audiências,
│                        #   tarefas, financeiro, relatórios e controle de acessos
├── ia/                  # Contém tasks e lógica de IA
├── templates/           # Contém static/ e templates globais (base + sidebar)
├── usuarios/            # Autenticação, clientes e documentos
├── manage.py            # Utilitário de linha de comando
├── requirements.txt     # Dependências do projeto
└── README.md            # Documentação
```

---

## 📚 Documentação Útil

- [Django Docs](https://docs.djangoproject.com/)
- [Python](https://www.python.org/)
- [Django-Q Docs](https://django-q.readthedocs.io/en/latest/) / [Celery Docs](https://docs.celeryq.dev/en/stable/)

---

## ⚠️ Aviso Legal

Este projeto não substitui a atuação de um advogado.
As informações geradas pelo sistema e pela IA servem apenas como apoio à análise jurídica.

---

## 📝 Licença

Este projeto está licenciado sob a **Apache License 2.0**.  
Versões anteriores do projeto utilizaram a **MIT License**.

**Sinta-se à vontade para estudar, modificar e evoluir o código.**

