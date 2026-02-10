---
title: Zoho Projects
layout: default
parent: Zoho Usage Guide
nav_order: 1
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
   - When recording expenses related to a project, select both the customer and project name for each transaction
   - **Tip**: Use bulk update to tag multiple expenses at once rather than updating each expense individually.

## How to Create a Project Report
1. **Navigate to Scheduled Reports**
   - Direct link: https://books.zoho.com/app/ORGNUMBER#/reports/scheduledlist?report_group=scheduledlist
   - Or navigate via: Zoho Books → Reports → Scheduled Reports
2. **Initialize a Custom Report**
   - Click the blue **Create Custom Report** button in the top right corner
   - When prompted for report type, select **Account Transactions**
3. **Configure Report Settings**
   **Basic Settings:**
   - **Date Range**: Select the date range for the cycle
     - GSS Fiscal Year: June 1 – May 31
     - Academic Year: September 1 – August 31
     - Calendar Year: January 1 – December 31
   - **Group By**: Leave ungrouped (select "None")
   
   **Advanced Filters:**
   - Filter by **Project Name** to show only transactions tagged to this project
   
   **Columns to Display:**
   - Date
   - Account
   - Debit
   - Description
   
   **Details to Display:**
   - Organization Name
   - Page Number
   - Organization Logo
   - Generated Date

4. **Set Report Name and Permissions**
   - **Report Title**: Use the project name (e.g., "AO Funding 25-26 FY")
   - **Configure Permissions**: Select "Share with Everyone"
   - Save the custom report
5. **Schedule Automated Delivery**
   - Set up monthly delivery on the **8th of every month**. This allows a full week after month-end for expenses to be approved and processed.
   - Add email recipients for relevant stakeholders.

## Example Use Case
For AO Funding tracking:
- A project named "AO Funding 25-26 FY" and customer "AO Funding" were created
- All AO-related expenses are tagged with this project when recorded
- A custom report runs monthly, summarizing cumulative AO expenses for the fiscal year
- The report is automatically sent to designated recipients and accessible anytime via Zoho Books

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
