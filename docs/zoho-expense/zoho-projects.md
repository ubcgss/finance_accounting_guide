---
title: Zoho Projects
layout: default
parent: Zoho Usage Guide
nav_order: 1
permalink: /zoho/projects/
---

# Zoho Projects

## Introduction to Zoho Projects 
- **What Are Zoho Projects?** Projects in Zoho Books allow you to track expenses and revenues associated with specific initiatives, events, or funding streams. By tagging transactions with a project name, you can easily automate spending monitoring, generate targeted reports, and maintain clear financial records for distinct activities (e.g., AO Funding, FSI programs, specific events). 
- **When to create a new project?** Create a new project when an existing initiative has a distinct funding source that needs separate tracking (e.g. FSI programs), or specific initiatives require separate tracking to know when funding has run out (e.g. GSFA funding).

{: .important }
> Projects follow the GSS fiscal year (June 1 — May 31). At the start of each fiscal year, create new projects for recurring initiatives with the updated year code.

## How to Create a New Project
1. **Navigate to Project Settings**
   - Go to the Zoho Expense organization project settings page: https://expense.zoho.com/app/ORGNUMBER#/settings/projects
   - Alternatively, access via: Settings → Projects
2. **Create a New Project**
   - Click the "New Project" or "Add Project" button
3. **Define the Project Name**
   - Use a clear, consistent naming convention that includes:
     - Project type
     - Time period
     - Cycle designation
   - **Naming Format**: `[Project Type] [Year Range] [Cycle Type]`
   - **Examples**:
     - "AO Funding 25-26 FY"
     - "MSP 25-26 AY"
     - "Orientation 2025 FY"
   - **Cycle Type Abbreviations**:
     - **AY** = Academic Year (September to August)
     - **FY** = GSS Fiscal Year (June to May)
     - **CY** = Calendar Year (January to December)
4. **Assign or Create a Customer**
   - Select an existing customer or create a new one
   - Use the **project type** as the customer name (e.g., for "AO Funding 25-26 FY", the customer should be "AO Funding")
   - This groups related projects under the same customer for easier tracking across multiple years\
5. **Associate With All Users**
- When prompted, tick the box to associate the project with all users, and save the project.

## Tagging Expenses Related to the Project
- When recording expenses related to a project, select both the **Customer** and **Project** name for each transaction.
- To tag multiple expenses at once, see [Project Tracking]({% link docs/zoho-expense/project-tracking.md %}) for the bulk-update workflow.
- To set up automated reports for a project, see [Project Reports]({% link docs/zoho-expense/project-reports.md %}).

<!--
## Project Naming Convention

All projects must follow this format:

```
ProjectNameF/AYear_MonthYear_Number
```

| Component | Description | Example |
|-----------|-------------|---------|
| `ProjectName` | Short name with no spaces | `BabyHamper` |
| `F/AYear` | Fiscal or academic year code | `2526AY` (for 2025-26) |
| `MonthYear` | Month and year of the report | `202510` (October 2025) |
| `Number` | Sequential number for that month | `1`, `2`, etc. |

**Full example**: `BabyHamper2526AY_202510_1` — the first Baby Hamper expense report for October 2025 in the 2025-26 academic year.

{: .tip }

> Be consistent with project names across the fiscal year. If you name the first report `MealSubsidy2526AY_202506_1`, all subsequent Meal Subsidy reports should start with `MealSubsidy2526AY`.
-->
