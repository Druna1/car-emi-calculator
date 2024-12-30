import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import math
import calendar

############################
# Utility Functions
############################

def format_inr(amount):
    """Format a number as Indian Rupees with commas and no decimals."""
    return f"₹ {amount:,.0f}"

############################
# Monthly EMI Calculation
############################

def calculate_car_emi(
    principal,
    annual_interest_rate,
    loan_tenure_years
):
    """
    Calculate the standard monthly EMI (Equated Monthly Installment)
    for a car loan using the formula:
      EMI = P * [r(1+r)^n] / [(1+r)^n - 1]
    Where:
      P = principal
      r = monthly interest (annual_interest / 12)
      n = number of months
    """
    monthly_interest_rate = (annual_interest_rate / 100.0) / 12.0
    total_months = loan_tenure_years * 12

    if total_months <= 0:
        return 0.0
    if monthly_interest_rate == 0:
        # Edge case: 0% interest
        return principal / total_months

    emi = (
        principal
        * monthly_interest_rate
        * (1 + monthly_interest_rate) ** total_months
    ) / (
        (1 + monthly_interest_rate) ** total_months - 1
    )
    return emi


############################
# Monthly Amortization Schedule
############################

def build_monthly_schedule(
    principal,
    annual_interest_rate,
    loan_tenure_years,
    monthly_prepayment=0.0,
    quarterly_prepayment=0.0,
    start_year=2024,
):
    """
    Build a month-by-month amortization schedule for the car loan, factoring in
    optional monthly & quarterly prepayments.

    Returns a DataFrame with columns:
      Year, MonthNum, MonthAbbr, OldBalance, InterestPaid, PrincipalPaid,
      Prepayment, NewBalance
    """
    monthly_interest_rate = (annual_interest_rate / 100.0) / 12.0
    total_months = loan_tenure_years * 12

    # Basic EMI
    emi = calculate_car_emi(principal, annual_interest_rate, loan_tenure_years)

    balance = principal
    data_rows = []
    current_month = 1

    while balance > 0 and current_month <= total_months:
        # Determine the calendar year and month (for display)
        year_offset = (current_month - 1) // 12
        this_year = start_year + year_offset
        month_index = (current_month - 1) % 12  # 0..11
        month_abbr = calendar.month_abbr[month_index + 1]

        # Interest portion
        interest_payment = balance * monthly_interest_rate
        principal_payment = emi - interest_payment

        # Prepayment
        prepay_amount = 0.0
        if monthly_prepayment > 0:
            prepay_amount += monthly_prepayment
        if (current_month % 3 == 0) and (quarterly_prepayment > 0):
            prepay_amount += quarterly_prepayment

        old_balance = balance
        # Deduct principal portion
        balance -= principal_payment
        # Deduct prepayment
        balance -= prepay_amount

        if balance < 0:
            balance = 0

        data_rows.append({
            "Year": this_year,
            "MonthNum": current_month,
            "MonthAbbr": month_abbr,
            "OldBalance": old_balance,
            "InterestPaid": interest_payment,
            "PrincipalPaid": principal_payment,
            "Prepayment": prepay_amount,
            "NewBalance": balance,
        })

        current_month += 1

    # Return as a DataFrame
    df_monthly = pd.DataFrame(data_rows)
    return df_monthly


############################
# Yearly Aggregation
############################

def aggregate_yearly(df_monthly, start_year, loan_tenure_years):
    """
    Given the monthly schedule, produce a yearly summary.
    Returns a DataFrame with columns:
      Year, PrincipalSum, PrepaymentSum, InterestSum, FinalBalance
    """
    # Group by Year
    if df_monthly.empty:
        # No data
        import numpy as np
        df_yearly = pd.DataFrame(columns=["Year","PrincipalSum","PrepaymentSum","InterestSum","FinalBalance"])
    else:
        def aggregator(x):
            return pd.Series({
                "PrincipalSum": x["PrincipalPaid"].sum(),
                "PrepaymentSum": x["Prepayment"].sum(),
                "InterestSum": x["InterestPaid"].sum(),
                "FinalBalance": x["NewBalance"].iloc[-1]
            })

        # Convert to int if needed
        df_monthly["Year"] = df_monthly["Year"].astype(int)
        df_yearly = df_monthly.groupby("Year").apply(aggregator).reset_index()

    # Merge with all possible years (in case the loan ends early)
    all_years = list(range(start_year, start_year + loan_tenure_years))
    df_all_years = pd.DataFrame({"Year": all_years})
    df_yearly = pd.merge(df_all_years, df_yearly, on="Year", how="left").fillna(0)
    df_yearly.sort_values("Year", inplace=True)

    # totalPayment = PrincipalSum + InterestSum + PrepaymentSum
    df_yearly["TotalPayment"] = df_yearly["PrincipalSum"] + df_yearly["InterestSum"] + df_yearly["PrepaymentSum"]
    # FinalBalance for each year is in "FinalBalance"
    # If it's negative, clamp to 0
    df_yearly["FinalBalance"] = df_yearly["FinalBalance"].apply(lambda x: max(0, x))

    return df_yearly


############################
# Streamlit Car EMI App
############################

def main():
    st.title("Car EMI Calculator with Partial Prepayments")

    # Inputs
    st.write("## Car Details & Loan Parameters")
    car_price = st.number_input("Car Price (₹)", min_value=1_00_000, step=50_000, value=5_00_000)
    down_payment_percentage = st.number_input("Down Payment (%)", min_value=0, max_value=100, step=1, value=10)
    annual_interest_rate = st.number_input("Annual Interest Rate (%)", min_value=0.0, step=0.1, value=9.0)
    loan_tenure_years = st.number_input("Loan Tenure (Years)", min_value=1, max_value=10, step=1, value=5)

    # Additional Fees or Car Loan Insurance
    insurance_or_fees = st.number_input("Insurance / Extra Fees (₹)", min_value=0, step=1000, value=0)
    start_year = st.number_input("Starting Year", min_value=2023, max_value=2100, step=1, value=2024)

    st.write("## Prepayments")
    monthly_prepay = st.number_input("Monthly Prepayment (₹)", min_value=0, step=1000, value=0)
    quarterly_prepay = st.number_input("Quarterly Prepayment (₹)", min_value=0, step=1000, value=0)
    one_time_prepay = st.number_input("One-time Prepayment (₹)", min_value=0, step=5000, value=0)

    if st.button("Calculate EMI"):
        # 1) Compute principal
        down_payment_amt = car_price * down_payment_percentage / 100.0
        principal_before_one_time = car_price - down_payment_amt - insurance_or_fees

        # Subtract one-time prepayment
        principal = principal_before_one_time - one_time_prepay
        if principal < 0:
            principal = 0

        # 2) Build monthly schedule
        df_monthly = build_monthly_schedule(
            principal=principal,
            annual_interest_rate=annual_interest_rate,
            loan_tenure_years=loan_tenure_years,
            monthly_prepayment=monthly_prepay,
            quarterly_prepayment=quarterly_prepay,
            start_year=start_year,
        )

        # 3) Aggregate yearly
        df_yearly = aggregate_yearly(df_monthly, start_year, loan_tenure_years)

        # 4) Summaries
        total_principal = df_yearly["PrincipalSum"].sum()
        total_prepayment = df_yearly["PrepaymentSum"].sum() + one_time_prepay
        total_interest = df_yearly["InterestSum"].sum()

        # Build a final DataFrame for the yearly schedule
        df_yearly["TaxesInsuranceMaintenance"] = 0  # For Car EMI, might skip or keep as 0
        df_yearly["PctLoanPaid"] = 0.0  # optional if you want a % of principal approach

        # If you want to compute a % of principal paid:
        #   (Cumulative principal + prepayment) / principal_before_one_time
        # (Be sure to clamp to 100 if balance is 0.)
        initial_car_loan_principal = principal_before_one_time
        df_yearly["CumulativePP"] = (df_yearly["PrincipalSum"].cumsum() + df_yearly["PrepaymentSum"].cumsum())
        if initial_car_loan_principal > 0:
            df_yearly["PctLoanPaid"] = ((df_yearly["CumulativePP"] / initial_car_loan_principal) * 100).clip(upper=100)
        else:
            df_yearly["PctLoanPaid"] = 100

        # Force 100% if the final balance is 0
        df_yearly.loc[df_yearly["FinalBalance"] <= 0, "PctLoanPaid"] = 100

        # Build a user-facing DataFrame
        schedule_df = pd.DataFrame({
            "Year": df_yearly["Year"].astype(int).astype(str),
            "Principal (₹)": df_yearly["PrincipalSum"].apply(format_inr),
            "Prepayments (₹)": df_yearly["PrepaymentSum"].apply(format_inr),
            "Interest (₹)": df_yearly["InterestSum"].apply(format_inr),
            "Total Payment (₹)": df_yearly["TotalPayment"].apply(format_inr),
            "Balance (₹)": df_yearly["FinalBalance"].apply(format_inr),
            "% of Loan Paid": df_yearly["PctLoanPaid"].apply(lambda x: f"{x:.2f}%"),
        })

        schedule_df.reset_index(drop=True, inplace=True)

        # 5) Summaries for display
        st.write("## Summary")
        st.write(f"**Car Price**: {format_inr(car_price)}")
        st.write(f"**Down Payment**: {format_inr(down_payment_amt)}")
        st.write(f"**Insurance / Extra Fees**: {format_inr(insurance_or_fees)}")
        st.write(f"**One-time Prepayment**: {format_inr(one_time_prepay)}")
        st.write(f"**Effective Car Loan Principal**: {format_inr(principal)}")

        st.write("---")
        st.write(f"**Total Principal Paid**: {format_inr(total_principal)}")
        st.write(f"**Total Prepayments**: {format_inr(total_prepayment)}")
        st.write(f"**Total Interest**: {format_inr(total_interest)}")

        # Pie Chart
        fig_pie, ax_pie = plt.subplots(figsize=(5,5))
        labels = ["Principal", "Prepayment", "Interest"]
        sizes = [total_principal, total_prepayment, total_interest]
        colors = ["#B0C4DE", "#FFB6C1", "#4169E1"]
        ax_pie.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=140)
        ax_pie.axis("equal")
        ax_pie.set_title("Car EMI Payment Breakdown")
        st.pyplot(fig_pie)

        # Bar Chart: Yearly Principal, Interest, Prepayment, plus dotted line for Balance
        fig_bar, ax_bar = plt.subplots(figsize=(8,5))
        years_numeric = df_yearly["Year"].astype(int).values
        principal_list = df_yearly["PrincipalSum"].values
        interest_list = df_yearly["InterestSum"].values
        prepay_list = df_yearly["PrepaymentSum"].values
        balance_list = df_yearly["FinalBalance"].values

        bar_width = 0.6
        ax_bar.bar(
            years_numeric,
            principal_list,
            color="#B0C4DE",
            label="Principal",
            width=bar_width
        )
        ax_bar.bar(
            years_numeric,
            interest_list,
            bottom=principal_list,
            color="#4169E1",
            label="Interest",
            width=bar_width
        )
        bottom_prepay = principal_list + interest_list
        ax_bar.bar(
            years_numeric,
            prepay_list,
            bottom=bottom_prepay,
            color="#FFB6C1",
            label="Prepayment",
            width=bar_width
        )
        # Plot dotted line for final balance
        ax_bar.plot(
            years_numeric,
            balance_list,
            'k--o',
            label="Remaining Balance"
        )
        ax_bar.set_xlabel("Year")
        ax_bar.set_ylabel("Amount (₹)")
        ax_bar.set_title("Car Loan Yearly Breakdown")
        ax_bar.legend()

        ax_bar.yaxis.set_major_formatter(
            ticker.FuncFormatter(lambda x, pos: f"₹{x:,.0f}")
        )

        st.pyplot(fig_bar)

        # Show the Yearly Table
        st.write("## Yearly Payment Schedule")
        st.dataframe(
            schedule_df.style
            .set_table_styles([
                {
                    'selector': 'th',
                    'props': [
                        ('background-color', '#5DADE2'),
                        ('color', 'white'),
                        ('font-weight', 'bold')
                    ]
                },
                {'selector': 'td', 'props': [('color', 'black')]},
            ])
        )

        # Monthly Breakdown
        if not df_monthly.empty:
            st.write("## Monthly Amortization Schedule")
            # Convert numeric columns to currency
            df_monthly_display = df_monthly.copy()
            for c in ["OldBalance","InterestPaid","PrincipalPaid","Prepayment","NewBalance"]:
                df_monthly_display[c] = df_monthly_display[c].apply(format_inr)

            df_monthly_display.reset_index(drop=True, inplace=True)

            st.dataframe(
                df_monthly_display.style
                .set_table_styles([
                    {
                        'selector': 'th',
                        'props': [
                            ('background-color', '#85C1E9'),
                            ('color', 'black'),
                            ('font-weight', 'bold')
                        ]
                    },
                    {'selector': 'td', 'props': [('color', 'black')]},
                ])
            )
        else:
            st.write("**No monthly data** (loan is 0 or ended instantly).")


if __name__ == "__main__":
    main()
