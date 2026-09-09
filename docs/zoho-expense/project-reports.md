---
title: Project Reports
layout: default
parent: Zoho Usage Guide
nav_order: 3
permalink: /zoho/project-reports/
---

# Project Reports

Once a project is set up and expenses are tagged (see [Zoho Projects]({% link docs/zoho-expense/zoho-projects.md %}) and [Project Tracking]({% link docs/zoho-expense/project-tracking.md %})), you can create automated reports in Zoho Books to monitor spending over time.

## How to Create a Project Report

1. **Navigate to Scheduled Reports**
   - Direct link: `Zoho Books → Reports → Scheduled Reports`
   - Or use: [https://books.zoho.com/app/ORGNUMBER#/reports/scheduledlist](https://books.zoho.com/app/ORGNUMBER#/reports/scheduledlist)
2. **Initialize a Custom Report**
   - Click the blue **Create Custom Report** button in the top right corner
   - When prompted for report type, select **Account Transactions**
3. **Configure Report Settings**

   **Basic Settings:**
   - **Date Range**: Select the range that matches the project's funding cycle. Use the full cycle so the report shows cumulative spending to date.

     | Project or funding stream | Report date range | Example for 2025–26 |
     |---|---|---|
     | GSFA | GSS fiscal year: June 1 – May 31 | June 1, 2025 – May 31, 2026 |
     | AO Funding | GSS fiscal year: June 1 – May 31 | June 1, 2025 – May 31, 2026 |
     | FSI | Academic year: September 1 – August 31 | September 1, 2025 – August 31, 2026 |

     For other projects, use the date range that matches the relevant funding agreement or project cycle.
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

{: .tip }
> Scheduling delivery on the 8th gives approvers a full week after month-end to process pending expenses before the report is generated.

## Example: AO Funding

For AO Funding tracking:
- A project named "AO Funding 25-26 FY" and customer "AO Funding" were created
- All AO-related expenses are tagged with this project when recorded
- A custom report runs monthly, summarizing cumulative AO expenses for the fiscal year
- The report is automatically sent to designated recipients and accessible anytime via Zoho Books
