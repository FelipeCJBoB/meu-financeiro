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


def _new_transaction_dialog(on_saved, *, editing=None) -> ui.dialog:
    """Same form serves creation and editing - a typo fix should not mean
    deleting and re-entering the whole transaction."""
    with get_session() as session:
        account_list = accounts_service.list_accounts(session)
        category_list = categories_service.list_categories(session)
        existing_splits = (
            transactions_service.transaction_splits(session, editing.id) if editing else []
        )

    account_options = {a.id: a.name for a in account_list}
    category_options = {c.id: c.name for c in category_list}

    with ui.dialog() as dialog, components.card(padding="1.25rem"):
        ui.label("Editar lançamento" if editing else "Novo lançamento").style(
            f"font-size:15px;font-weight:500;color:{theme.var('text')};margin-bottom:6px"
        )

        type_select = ui.select(
            dict(TYPE_LABELS),
            value=editing.type.value if editing and editing.type.value in TYPE_LABELS else "expense",
            label="Tipo",
        ).props("outlined dense").style("width:100%")
        desc_input = ui.input(
            "Descrição", value=editing.description if editing else ""
        ).props("outlined dense").style("width:100%")

        default_date = (
            editing.date
            if editing
            else (
                date.today()
                if state.is_current_cycle()
                else month_bounds(state.current_month(), state.cycle_start_day())[0]
            )
        )
        date_input = ui.input("Data", value=default_date.isoformat()).props(
            "outlined dense type=date"
        ).style("width:100%")
        month_warning = ui.label("").style(
            f"font-size:14px;color:{theme.var('amber')};display:none"
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

        already_settled_checkbox = ui.checkbox(
            "Ja paga - nao descontar do saldo atual",
            value=bool(editing and editing.already_settled),
        )
        already_settled_checkbox.tooltip(
            "Para uma despesa antiga que voce ja pagou e que ja esta refletida no "
            "saldo atual (por exemplo depois de usar Ajustar saldo em Patrimonio). "
            "Sem isso, lancar aqui descontaria o valor de novo."
        )
        already_settled_checkbox.set_visibility(
            (editing.type if editing else TransactionType(type_select.value))
            == TransactionType.expense
        )

        account_select = ui.select(
            account_options,
            value=editing.account_id if editing else next(iter(account_options), None),
            label="Conta",
        ).props("outlined dense").style("width:100%")

        transfer_select = ui.select(
            account_options,
            value=editing.transfer_account_id if editing else None,
            label="Conta destino",
        ).props("outlined dense").style("width:100%")
        transfer_select.set_visibility(
            bool(editing and editing.type == TransactionType.transfer)
        )

        category_block = ui.column().style("width:100%;gap:4px")
        category_block.set_visibility(
            not (editing and editing.type == TransactionType.transfer)
        )
        with category_block:
            category_select = ui.select(
                dict(category_options),
                value=editing.category_id if editing else None,
                label="Categoria",
            ).props("outlined dense").style("width:100%")

            # Sits right under the select, not after the split UI - the split
            # dropdown's own open overlay used to cover this button entirely,
            # so users who wanted a category that didn't exist yet could not
            # find where to add one.
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

            ui.button("Criar categoria", icon="add", on_click=_toggle_new_cat).props(
                "flat dense no-caps"
            ).style(f"color:{theme.var('accent2')};font-size:14px;align-self:flex-start")

            split_checkbox = ui.checkbox(
                "Dividir em mais de uma categoria", value=bool(existing_splits)
            )

            split_rows: list[dict] = []
            split_container = ui.column().style("width:100%;gap:6px")
            split_container.set_visibility(bool(existing_splits))

            def _add_split_row(category_id=None, amount_cents=0) -> None:
                with split_container:
                    with ui.row().style("width:100%;gap:6px;align-items:center") as row:
                        cat = ui.select(
                            dict(category_options), value=category_id, label="Categoria"
                        ).props("outlined dense").style("flex:1.4")
                        val = ui.number(
                            "Valor", value=amount_cents / 100 if amount_cents else 0, format="%.2f"
                        ).props("outlined dense").style("flex:1")

                        def _remove(row=row) -> None:
                            split_container.remove(row)
                            split_rows[:] = [r for r in split_rows if r["row"] is not row]

                        ui.button(icon="close", on_click=_remove).props("flat dense round")
                split_rows.append({"row": row, "category": cat, "amount": val})

            for split in existing_splits:
                _add_split_row(split.category_id, split.amount_cents)

            if existing_splits:
                category_select.set_visibility(False)

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
                    f"color:{theme.var('accent2')};font-size:14px"
                )

        amount_input = ui.number(
            "Valor total (R$)",
            value=editing.amount_cents / 100 if editing else 0,
            format="%.2f",
        ).props("outlined dense").style("width:100%")

        recurring_checkbox = ui.checkbox("Lançamento recorrente")
        frequency_select = ui.select(dict(FREQ_LABELS), value="monthly", label="Frequência").props(
            "outlined dense"
        ).style("width:100%")
        frequency_select.set_visibility(False)
        recurring_checkbox.on_value_change(lambda e: frequency_select.set_visibility(e.value))

        rule_checkbox = ui.checkbox("Sempre categorizar esta descrição assim")

        if editing:
            recurring_checkbox.set_visibility(False)
            frequency_select.set_visibility(False)
            rule_checkbox.set_visibility(False)

        def _on_type_change(e) -> None:
            is_transfer = e.value == "transfer"
            transfer_select.set_visibility(is_transfer)
            category_block.set_visibility(not is_transfer)
            already_settled_checkbox.set_visibility(e.value == "expense")

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
                    if editing:
                        transactions_service.update_transaction(
                            s2,
                            editing.id,
                            date_=date.fromisoformat(date_input.value),
                            description=desc_input.value,
                            account_id=account_select.value,
                            type_=type_value,
                            amount_cents=total_cents,
                            category_id=category_select.value if type_value != TransactionType.transfer else None,
                            transfer_account_id=transfer_select.value if type_value == TransactionType.transfer else None,
                            splits=splits,
                            already_settled=(
                                already_settled_checkbox.value
                                if type_value == TransactionType.expense
                                else False
                            ),
                        )
                        dialog.close()
                        on_saved()
                        return

                    tx = transactions_service.create_transaction(
                        s2,
                        date_=date.fromisoformat(date_input.value),
                        description=desc_input.value,
                        account_id=account_select.value,
                        type_=type_value,
                        amount_cents=total_cents,
                        category_id=category_select.value if type_value != TransactionType.transfer else None,
                        transfer_account_id=transfer_select.value if type_value == TransactionType.transfer else None,
                        already_settled=(
                            already_settled_checkbox.value
                            if type_value == TransactionType.expense
                            else False
                        ),
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

        def _delete() -> None:
            with get_session() as s2:
                transactions_service.delete_transaction(s2, editing.id)
            dialog.close()
            on_saved()

        with ui.row().style(
            "justify-content:space-between;gap:8px;margin-top:14px;width:100%;flex-wrap:wrap"
        ):
            if editing:
                ui.button("Excluir", icon="delete", on_click=_delete).props(
                    "flat no-caps dense"
                ).style(f"color:{theme.var('red')}")
            else:
                ui.element("div")
            with ui.row().style("gap:8px"):
                ui.button("Cancelar", on_click=dialog.close).props("flat no-caps").style(
                    f"color:{theme.var('text2')}"
                )
                ui.button(
                    "Salvar alterações" if editing else "Salvar lançamento", on_click=_save
                ).props("no-caps unelevated").style(
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
                    ui.label(rule.description).style(f"font-size:15px;color:{theme.var('text')}")
                    ui.label(
                        f"Vencido em {rule.next_due_date.strftime('%d/%m/%Y')} · {format_brl(rule.amount_cents)}"
                    ).style(f"font-size:13px;color:{theme.var('textm')}")

                def _skip(rule_id=rule.id) -> None:
                    with get_session() as s2:
                        recurring_service.skip_recurring(s2, rule_id)
                    on_changed()

                confirm_dialog = components.confirm_recurring_dialog(rule, on_changed)
                ui.button("Confirmar", on_click=confirm_dialog.open).props(
                    "dense no-caps unelevated"
                ).style(f"background:{theme.var('accent')};color:{theme.var('s1')}")
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
            account_id=state.account_id(),
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
            with ui.row().style("align-items:center;gap:8px;flex-wrap:wrap"):
                components.month_navigator()
                components.account_filter_selector()
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
            if tx.already_settled:
                sub += " · ja paga, fora do saldo"

        with ui.column().style("flex:1;gap:0"):
            ui.label(tx.description).style(f"font-size:15px;color:{theme.var('text')}")
            ui.label(f"{tx.date.strftime('%d/%m/%Y')} · {sub}").style(
                f"font-size:13px;color:{theme.var('textm')}"
            )

        if tx.type == TransactionType.income:
            color, sign, shown_cents = theme.var("green"), "+", tx.amount_cents
        elif tx.type == TransactionType.transfer:
            color, sign, shown_cents = theme.var("text2"), "", tx.amount_cents
        elif tx.type == TransactionType.adjustment:
            color = theme.var("green") if tx.amount_cents >= 0 else theme.var("red")
            sign = "+" if tx.amount_cents >= 0 else "-"
            shown_cents = abs(tx.amount_cents)
        else:
            color, sign, shown_cents = theme.var("red"), "-", tx.amount_cents
        ui.label(f"{sign}{format_brl(shown_cents)}").style(f"font-size:15px;color:{color}")

        if tx.type == TransactionType.adjustment:
            ui.element("div").style("width:32px")
        else:
            edit_dialog = _new_transaction_dialog(
                lambda: ui.navigate.reload(), editing=tx
            )
            ui.button(icon="edit", on_click=edit_dialog.open).props(
                "flat dense round"
            ).style(f"color:{theme.var('textm')}").tooltip("Editar ou excluir")
