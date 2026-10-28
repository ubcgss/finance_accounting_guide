---
title: Budget Categories
layout: default
parent: Zoho Usage Guide
nav_order: 6
permalink: /zoho/budget-categories/
---

# Budget Categories

This page helps you choose the correct **Budget Line** (the expense category in Zoho) for each expense, and the **Budget Category** to use in the report title. Search for what you bought, or browse the tables below. If nothing is a clear fit, ask the Financial Officer before using an "Other Expenses" line.

{: .important }
> From June 1, 2026 (fiscal year 2026-27), all budget lines use **4-digit codes**. The old 3-digit codes are inactive in Zoho. The "Formerly" column shows the old budget code for reference.

{% include budget_search.html %}

{% assign lines = site.data.budget_lines.lines %}
{% for category in site.data.budget_lines.categories %}
{% assign category_lines = lines | where: "budget_category", category.name | where: "finance_only", false %}
{% if category_lines.size > 0 %}
## {{ category.name }}

{{ category.summary }}

| Code | Budget Line | Formerly | Use for | Examples |
|------|-------------|----------|---------|----------|
{% for line in category_lines %}| `{{ line.code }}` | {{ line.name }} | {{ line.formerly }} | {{ line.usage }} | {% for example in line.examples %}{{ example.text }}{% unless forloop.last %}; {% endunless %}{% endfor %} |
{% endfor %}
{% endif %}
{% endfor %}

## Common mix-ups

| If it is... | Use | Not |
|-------------|-----|-----|
| Food or a room for a **meeting** of executives, Council or a committee | `6640` / `6650` / `6660` Meeting Expenses | `6320` Event Costs |
| Food or supplies for a GSS **event** open to members | `6320` Event Costs (`6330` for orientation) | Meeting Expenses |
| Honorarium for an elected executive | `6070` Executive Honoraria | `6080` |
| Honorarium for the Council Chair, Speaker or an appointed chair | `6080` Council Chair & Speaker Honoraria | `6070` |
| Software, apps, cloud services, domains | `6560` IT Services and Digital Subscriptions | `6540` Office Supplies |
| Posters, ads, branded giveaways | `6570` Marketing, Advertising & Promotion | `6320` Event Costs |
| A contractor or outside professional's invoice | `6200` Professional & Contracted Services | a Program or Event line |
| Meal subsidy program purchases | `6340` Meal Subsidy Program Costs | `7410` Grant 1 – FSI |
| Food, venue or activities at an executive retreat | `6610` Executive Retreat | `6640` Meeting Expenses - Executives |
| Health spending account (HSA) claim charges | `6030` / `6040` Employee Benefits | `6990` Other Expenses |

## Finance-only lines

The Financial Officer posts to these lines through payroll, journal entries or year-end adjustments. Do not pick them for an expense report.

{% assign finance_lines = lines | where: "finance_only", true %}
| Code | Budget Line | What it holds |
|------|-------------|---------------|
{% for line in finance_lines %}| `{{ line.code }}` | {{ line.name }} | {{ line.usage }} |
{% endfor %}

{: .note }
> Use `6990` Other Expenses - Operating or `7990` Other Expenses - Restricted only when no specific line fits, and check with the Financial Officer first.
