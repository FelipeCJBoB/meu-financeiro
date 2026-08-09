# Meu financeiro

Controle financeiro pessoal, desktop, com os dados 100% na sua máquina — sem nuvem, sem assinatura, sem conta de terceiro guardando seu extrato.

Nasceu de uma necessidade real: depois de um aumento salarial, faltava uma visão clara de quanto entra, quanto sai e quanto sobra — sem depender de um app de terceiros para lidar com dados financeiros sensíveis.

## Stack

- **Python 3.10+**
- **[NiceGUI](https://nicegui.io/)** — interface, rodando como janela desktop nativa (WebView2)
- **[SQLModel](https://sqlmodel.tiangolo.com/) + SQLite** — banco de dados local, sem servidor
- **[Plotly](https://plotly.com/python/)** — gráficos
- **PyInstaller** — empacotamento em um único `.exe` standalone (não exige Python instalado na máquina de destino)

## Funcionalidades

### Dashboard
- KPIs do ciclo: disponível para gastar, patrimônio líquido, fluxo do mês, ritmo de gasto projetado
- Orçamento diário: quanto ainda dá pra gastar por dia até o fim do ciclo
- Banner de exceção — só aparece quando há algo que precisa de atenção (conta atrasada, categoria estourada); fica ausente quando está tudo em ordem
- Diagrama de fluxo (Sankey) mostrando para onde foi o dinheiro no mês
- Comparativo receitas vs. despesas dos últimos 6 ciclos
- Próximos pagamentos agendados (recorrências a vencer)
- Navegador de mês/ciclo, com comparação automática contra o ciclo anterior

### Lançamentos
- Receita, despesa ou transferência entre contas
- Criação de categoria nova direto no formulário — ícone, cor e tipo, sem sair da tela
- Sugestão automática de categoria a partir do histórico de descrições, com opção de virar regra permanente
- Divisão de um único lançamento em mais de uma categoria
- Lançamentos recorrentes, com confirmação de valor editável (útil para contas que variam mês a mês, como luz ou água)
- Aviso quando a data escolhida cai fora do mês que você está vendo

### Orçamento
- Comparação orçado vs. gasto por categoria, em gráfico e em lista editável
- Projeção de ritmo: no ritmo atual, você vai fechar dentro ou fora do orçamento?

### Metas
- Progresso com marcador de ritmo esperado (onde você deveria estar hoje, considerando o prazo) — não só o percentual bruto

### Patrimônio
- Evolução do patrimônio em barras (quanto foi aportado vs. quanto foi ganho/perdido em valorização)
- Composição atual por conta
- Projeção de saldo para os próximos 30/60/90 dias, baseada nas recorrências já cadastradas, com faixa de incerteza calculada a partir da variação real das suas despesas

### Configurações
- Ciclo financeiro customizável — define o dia do mês em que seu "mês financeiro" começa (ex: o dia do salário), em vez de depender do dia 1 fixo
- Dois temas (Linen, claro e aconchegante; Dusk, escuro)
- Presets de tamanho de janela (2K / Full HD)

## Rodando localmente

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

## Gerando o executável

```powershell
.\build.ps1
```

Gera `dist\MeuFinanceiro.exe` — um único arquivo, sem instalador, sem exigir Python na máquina de destino.

## Estrutura do projeto

```
app/
  models.py       modelos de dados (SQLModel): contas, transações, categorias,
                  orçamentos, metas, recorrências, configurações
  db.py           engine SQLite + migrações aditivas seguras (nunca perde dado
                  existente ao adicionar uma coluna nova)
  state.py        estado de navegação (mês/ciclo em exibição)
  theme.py        temas Linen / Dusk
  services/       regras de negócio puras — sem NiceGUI, testáveis isoladamente
  ui/             telas e componentes NiceGUI
run.py            ponto de entrada usado pelo PyInstaller
```

## Dados

Tudo fica em `%APPDATA%\MeuFinanceiro\dados.db` (SQLite). Nada é enviado pra fora da sua máquina.

## Licença

MIT — veja [LICENSE](LICENSE).
