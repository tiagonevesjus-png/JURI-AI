# Catálogo funcional de referência — JURI-AI

Este documento descreve capacidades que o JURI-AI pode oferecer a partir de
uma análise funcional de sistemas de gestão jurídica. É uma especificação
original: não reproduz artigos, textos, tutoriais ou identidade de terceiros.

## Princípios de implementação

- Fontes oficiais e dados privados permanecem separados e auditáveis.
- Uma automação nunca protocola, assina, toma ciência ou cria prazo fatal sem
  confirmação humana.
- Cada registro importado indica fonte, data da coleta e vínculo com o
  processo interno.
- Processos sem cliente certo entram em fila de conferência.

## Mapa de capacidades

| Área | Operação no JURI-AI | Situação |
| --- | --- | --- |
| Painel diário | Publicações, movimentações relevantes, prazos, audiências, e-mails e tarefas | Implementado em `/hoje/` |
| Expediente | Central unificada de alertas e triagens por prioridade | Implementado parcialmente; evoluir filtros e responsáveis |
| Processos | Carteira, detalhes, movimentações, fonte DataJud e importação auditável | Implementado |
| Coleta externa | PJe/eLaw/DataJud em fila de conferência com deduplicação CNJ | Implementado |
| Agenda | Audiências, compromissos e sincronização de leitura com Google Agenda | Implementado |
| Clientes | Cadastro, vínculo com processos, compromissos e financeiro | Implementado |
| Documentos | Repositório de documentos por cliente/processo com metadados | Estrutura básica existente |
| Assinatura | Preparação de PDF e validação assistida por PJeOffice/DesktopID | Implementado, sem guardar chave privada ou PIN |
| Prazos | Registro confirmado, marcos de alerta e trilha de auditoria | Implementado; feriados locais são próxima evolução |
| Financeiro | Receitas, despesas, honorários, custas e visão por cliente | Implementado |
| Peças | Rascunho assistido por IA, versão, revisão e exportação | Planejado |
| Relatórios | Carteira, produtividade, prazos, andamento e financeiro | Estrutura inicial existente |
| Base de conhecimento | Artigos originais, checklists, modelos e procedimentos internos | Planejado |

## Fluxos prioritários

### 1. Processo novo

1. Receber número CNJ via importação, formulário ou fonte oficial.
2. Normalizar o número, remover duplicidades e identificar tribunal.
3. Vincular somente quando o cliente estiver confirmado.
4. Consultar DataJud e DJEN em rotinas de leitura.
5. Triar eventos e abrir alerta único por processo.

### 2. Expediente do dia

1. Consolidar DJEN, DataJud, Gmail e Agenda.
2. Deduplicar por processo, evento e período.
3. Classificar por impacto: prazo, audiência, sentença, recurso, juntada ou informativo.
4. Exibir providência sugerida e exigir conferência para prazo.
5. Distribuir alertas por painel, e-mail, Telegram, WhatsApp ou push.

### 3. Documento e assinatura

1. Criar minuta e anexos com versão e processo vinculado.
2. Validar tipo, hash e ordem dos arquivos.
3. Preparar para assinatura local no PJeOffice/DesktopID.
4. Exigir autorização no fluxo oficial do certificado em nuvem.
5. Registrar recibo, hash e metadados públicos do certificado.

## Próximas entregas técnicas

1. Página **Expediente** com fila de alertas e responsável.
2. Página **Documentos** com filtros por cliente e processo.
3. Página **Peças** com modelos próprios, rascunho por IA e revisão humana.
4. Base de conhecimento própria com artigos curtos, checklists e links para
   fontes oficiais.
5. Regras de feriados nacionais, estaduais e locais para auxiliar a conferência
   de prazos — sem substituir a validação profissional.
