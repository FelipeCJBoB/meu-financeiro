from __future__ import annotations

from datetime import date

from nicegui import ui

from app import state, theme
from app.db import get_session
from app.models import CategoryKind, Frequency, TransactionType
from app.services import accounts as accounts_service
from app.services import categories as categories_service
from app.services import recurring as recurring_service
from app.services import transactions as transactions_service
from app.services.money import (
    format_brl,
    format_month_label,
    month_bounds,
    month_key_for_date,
    to_cents,
)
from app.ui import components
from app.ui.layout import page_frame

TYPE_LABELS = {"expense": "Despesa", "income": "Receita", "transfer": "Transferência"}
FREQ_LABELS = {"weekly": "Semanal", "monthly": "Mensal", "yearly": "Anual"}
CATEGORY_ICON_OPTIONS = {
    "home": "Casa",
    "shopping_cart": "Compras",
    "directions_car": "Transporte",
    "movie": "Lazer",
    "favorite": "Saude",
    "school": "Educacao",
    "account_balance": "Banco",
    "paid": "Dinheiro",
    "fitness_center": "Academia",
    "pets": "Pet",
    "flight": "Viagem",
    "sell": "Outro",
}


def _new_transaction_dialog(on_saved) -> ui.dialog:
    with get_session() as session:
        account_list = accounts_service.list_accounts(session)
        category_list = categories_service.list_categories(session)

    account_options = {a.id: a.name for a in account_list}
    category_options = {c.id: c.name for c in category_list}

    with ui.dialog() as dialog, components.card(padding="1.25rem"):
        ui.label("Novo lançamento").style(
            f"font-size:15px;font-weight:500;color:{theme.var('text')};margin-bottom:6px"
        )

        type_select = ui.select(dict(TYPE_LABELS), value="expense", label="Tipo").props(
            "outlined dense"
        ).style("width:100%")
        desc_input = ui.input("Descrição").props("outlined dense").style("width:100%")

        default_date = (
            date.today()
            if state.is_current_cycle()
            else month_bounds(state.current_month(), state.cycle_start_day())[0]
        )
        date_input = ui.input("Data", value=default_date.isoformat()).props(
            "outlined dense type=date"
        ).style("width:100%")
        month_warning = ui.label("").style(
            f"font-size:12px;color:{theme.var('amber')};display:none"
        )

        def _check_month_warning() -> None:
            try:
                picked = date.fromisoformat(date_input.value)
            except (TypeError, ValueError):
                return
            picked_month = month_key_for_date(picked, state.cycle_start_day())
            if picked_month != state.current_month():
                month_warning.text = (
                    f"Este lançamento sera contado em {format_month_label(picked_month)}, "
                    f"nao no mes que voce esta vendo ({format_month_label(state.current_month())})."
                )
                month_warning.style("display:block")
            else:
                month_warning.style("display:none")

        date_input.on("change", _check_month_warning)
        _check_month_warning()

        account_select = ui.select(
            account_options,
            value=next(iter(account_options), None),
            label="Conta",
        ).props("outlined dense").style("width:100%")

        transfer_select = ui.select(account_options, label="Conta destino").props(
            "outlined dense"
        ).style("width:100%")
        transfer_select.set_visibility(False)

        category_block = ui.column().style("width:100%;gap:4px")
        with category_block:
            category_select = ui.select(dict(category_options), label="Categoria").props(
                "outlined dense"
            ).style("width:100%")

            split_checkbox = ui.checkbox("Dividir em mais de uma categoria")

            split_rows: list[dict] = []
            split_container = ui.column().style("width:100%;gap:6px")
            split_container.set_visibility(False)

            def _add_split_row() -> None:
                with split_container:
                    with ui.row().style("width:100%;gap:6px;align-items:center") as row:
                        cat = ui.select(dict(category_options), label="Categoria").props(
                            "outlined dense"
                        ).style("flex:1.4")
                        val = ui.number("Valor", value=0, format="%.2f").props(
                            "outlined dense"
                        ).style("flex:1")

                        def _remove(row=row) -> None:
                            split_container.remove(row)
                            split_rows[:] = [r for r in split_rows if r["row"] is not row]

                        ui.button(icon="close", on_click=_remove).props("flat dense round")
                split_rows.append({"row": row, "category": cat, "amount": val})

            def _toggle_split(e) -> None:
                split_container.set_visibility(e.value)
                category_select.set_visibility(not e.value)
                if e.value and not split_rows:
                    _add_split_row()
                    _add_split_row()

            split_checkbox.on_value_change(_toggle_split)

            with ui.row().style("width:100%;justify-content:space-between;align-items:center"):
                ui.button("+ Adicionar divisão", on_click=_add_split_row).props(
                    "flat dense no-caps"
                ).bind_visibility_from(split_checkbox, "value").style(
                    f"color:{theme.var('accent2')};font-size:12px"
                )

            new_cat_visible = {"value": False}
            new_cat_row = ui.column().style("width:100%;gap:6px")
            new_cat_row.set_visibility(False)
            with new_cat_row:
                new_cat_name = ui.input("Nome da nova categoria").props(
                    "outlined dense"
                ).style("width:100%")
                with ui.row().style("width:100%;gap:6px"):
                    new_cat_icon = ui.select(
                        dict(CATEGORY_ICON_OPTIONS), value="sell", label="Icone"
                    ).props("outlined dense").style("flex:1")
                    new_cat_kind = ui.select(
                        {"expense": "Despesa", "income": "Receita", "both": "Ambos"},
                        value="expense",
                        label="Tipo",
                    ).props("outlined dense").style("flex:1")
                new_cat_color = ui.color_input(value="#8ab4e8", label="Cor").props(
                    "outlined dense"
                ).style("width:100%")

                def _save_category() -> None:
                    if not new_cat_name.value:
                        ui.notify("Informe um nome", color="negative")
                        return
                    with get_session() as s2:
                        category = categories_service.get_or_create_category(
                            s2,
                            name=new_cat_name.value,
                            icon=new_cat_icon.value,
                            color=new_cat_color.value,
                            kind=CategoryKind(new_cat_kind.value),
                        )
                    category_options[category.id] = category.name
                    category_select.set_options(dict(category_options), value=category.id)
                    new_cat_row.set_visibility(False)
                    new_cat_name.value = ""

                ui.button("Salvar categoria", on_click=_save_category).props(
                    "unelevated no-caps dense"
                ).style(f"background:{theme.var('accent')};color:{theme.var('s1')}")

            def _toggle_new_cat() -> None:
                new_cat_visible["value"] = not new_cat_visible["value"]
                new_cat_row.set_visibility(new_cat_visible["value"])

            ui.button("+ Criar categoria", on_click=_toggle_new_cat).props(
                "flat dense no-caps"
            ).style(f"color:{theme.var('accent2')};font-size:12px;align-self:flex-start")

        amount_input = ui.number("Valor total (R$)", value=0, format="%.2f").props(
            "outlined dense"
        ).style("width:100%")

        recurring_checkbox = ui.checkbox("Lançamento recorrente")
        frequency_select = ui.select(dict(FREQ_LABELS), value="monthly", label="Frequência").props(
            "outlined dense"
        ).style("width:100%")
        frequency_select.set_visibility(False)
        recurring_checkbox.on_value_change(lambda e: frequency_select.set_visibility(e.value))

        rule_checkbox = ui.checkbox("Sempre categorizar esta descrição assim")

        def _on_type_change(e) -> None:
            is_transfer = e.value == "transfer"
            transfer_select.set_visibility(is_transfer)
            category_block.set_visibility(not is_transfer)

        type_select.on_value_change(_on_type_change)

        async def _on_desc_blur() -> None:
            if category_select.value or type_select.value == "transfer":
                return
            with get_session() as s2:
                suggestion = categories_service.suggest_category(s2, desc_input.value or "")
            if suggestion:
                category_select.value = suggestion.id

        desc_input.on("blur", _on_desc_blur)

        def _save() -> None:
            if not desc_input.value:
                ui.notify("Informe uma descrição", color="negative")
                return
            if not account_select.value:
                ui.notify("Crie uma conta antes de lançar", color="negative")
                return

            type_value = TransactionType(type_select.value)
            total_cents = to_cents(amount_input.value or 0)
            splits = None

            if split_checkbox.value:
                splits = []
                for entry in split_rows:
                    if entry["category"].value and entry["amount"].value:
                        splits.append(
                            {
                                "category_id": entry["category"].value,
                                "amount_cents": to_cents(entry["amount"].value),
                            }
                        )
                if not splits:
                    ui.notify("Preencha ao menos uma divisão", color="negative")
                    return

            try:
                with get_session() as s2:
                    tx = transactions_service.create_transaction(
                        s2,
                        date_=date.fromisoformat(date_input.value),
                        description=desc_input.value,
                        account_id=account_select.value,
                        type_=type_value,
                        amount_cents=total_cents,
                        category_id=category_select.value if type_value != TransactionType.transfer else None,
                        transfer_account_id=transfer_select.value if type_value == TransactionType.transfer else None,
                        splits=splits,
                    )

                    if rule_checkbox.value and category_select.value and type_value != TransactionType.transfer:
                        categories_service.add_rule(
                            s2, match_text=desc_input.value, category_id=category_select.value
                        )

                    if recurring_checkbox.value:
                        next_due = recurring_service.advance_date(
                            date.fromisoformat(date_input.value), frequency_select.value
                        )
                        rule = recurring_service.create_recurring_rule(
                            s2,
                            description=desc_input.value,
                            account_id=account_select.value,
                            type_=type_value,
                            amount_cents=total_cents,
                            frequency=Frequency(frequency_select.value),
                            next_due_date=next_due,
                            category_id=category_select.value if type_value != TransactionType.transfer else None,
                        )
                        tx.recurring_rule_id = rule.id
                        s2.add(tx)
                        s2.commit()
            except transactions_service.TransactionError as exc:
                ui.notify(str(exc), color="negative")
                return

            dialog.close()
            on_saved()

        with ui.row().style("justify-content:flex-end;gap:8px;margin-top:14px;width:100%"):
            ui.button("Cancelar", on_click=dialog.close).props("flat no-caps").style(
                f"color:{theme.var('text2')}"
            )
            ui.button("Salvar lançamento", on_click=_save).props("no-caps unelevated").style(
                f"background:{theme.var('accent')};color:{theme.var('s1')}"
            )

    return dialog


def _due_recurring_section(session, on_changed) -> None:
    due = recurring_service.due_recurring_rules(session)
    if not due:
        return
    with components.card():
        components.section_label("Recorrências pendentes")
        for rule in due:
            with ui.row().style(
                f"width:100%;align-items:center;gap:10px;padding:8px 0;"
                f"border-bottom:0.5px solid {theme.var('border')}"
            ):
                with ui.column().style("flex:1;gap:0"):
                    ui.label(rule.description).style(f"font-size:13px;color:{theme.var('text')}")
                    ui.label(
                        f"Vencido em {rule.next_due_date.strftime('%d/%m/%Y')} · {format_brl(rule.amount_cents)}"
                    ).style(f"font-size:11px;color:{theme.var('textm')}")

                def _confirm(rule_id=rule.id) -> None:
                    with get_session() as s2:
                        recurring_service.confirm_recurring(s2, rule_id)
                    on_changed()

                def _skip(rule_id=rule.id) -> None:
                    with get_session() as s2:
                        recurring_service.skip_recurring(s2, rule_id)
                    on_changed()

                ui.button("Confirmar", on_click=_confirm).props("dense no-caps unelevated").style(
                    f"background:{theme.var('accent')};color:{theme.var('s1')}"
                )
                ui.button("Pular", on_click=_skip).props("dense no-caps flat").style(
                    f"color:{theme.var('text2')}"
                )


@ui.refreshable
def _transaction_list(show_all: bool) -> None:
    month = state.current_month()
    start, end = month_bounds(month, state.cycle_start_day())
    with get_session() as session:
        items = transactions_service.list_transactions(
            session,
            start=None if show_all else start,
            end=None if show_all else end,
            limit=200,
        )
        with components.card():
            if not items:
                components.empty_state(
                    "Nenhum lançamento ainda" if show_all else "Nenhum lançamento neste mes",
                    icon="receipt_long",
                )
            for tx in items:
                _row(session, tx)


def render() -> None:
    with page_frame("/lancamentos"):
        with get_session() as session:
            all_accounts = accounts_service.list_accounts(session)
            if not all_accounts:
                with components.card(padding="2rem"):
                    components.empty_state(
                        "Crie uma conta primeiro em Patrimônio.", icon="account_balance_wallet"
                    )
                return

            _due_recurring_section(session, lambda: ui.navigate.reload())

        with ui.row().style(
            "width:100%;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px"
        ):
            components.month_navigator()
            with ui.row().style("gap:8px;align-items:center"):
                show_all = ui.checkbox(
                    "Ver todo o historico",
                    on_change=lambda e: _transaction_list.refresh(e.value),
                )
                dialog = _new_transaction_dialog(lambda: ui.navigate.reload())
                ui.button("Novo lançamento", icon="add", on_click=dialog.open).props(
                    "no-caps unelevated"
                ).style(f"background:{theme.var('accent')};color:{theme.var('s1')}")

        _transaction_list(show_all.value)


def _row(session, tx) -> None:
    from app.models import Category

    with ui.row().style(
        f"width:100%;align-items:center;gap:10px;padding:9px 0;"
        f"border-bottom:0.5px solid {theme.var('border')}"
    ):
        if tx.type == TransactionType.transfer:
            components.category_chip("swap_horiz", theme.current()["accent2"])
            sub = "Transferência"
        elif tx.type == TransactionType.adjustment:
            components.category_chip("tune", theme.current()["textm"])
            sub = "Ajuste de saldo"
        else:
            category = session.get(Category, tx.category_id) if tx.category_id else None
            components.category_chip(
                category.icon if category else "receipt_long",
                category.color if category else theme.current()["textm"],
            )
            sub = category.name if category else "Dividido em categorias"

        with ui.column().style("flex:1;gap:0"):
            ui.label(tx.description).style(f"font-size:13px;color:{theme.var('text')}")
            ui.label(f"{tx.date.strftime('%d/%m/%Y')} · {sub}").style(
                f"font-size:11px;color:{theme.var('textm')}"
            )

        if tx.type == TransactionType.income:
            color, sign = theme.var("green"), "+"
        elif tx.type in (TransactionType.transfer, TransactionType.adjustment):
            color, sign = theme.var("text2"), ""
        else:
            color, sign = theme.var("red"), "-"
        ui.label(f"{sign}{format_brl(tx.amount_cents)}").style(f"font-size:13px;color:{color}")
