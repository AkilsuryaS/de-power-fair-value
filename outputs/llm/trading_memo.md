# DE-LU Day-Ahead Power Fair-Value Memo – 2025-12-31

**1. Signal Summary**  
The hist_gradient_boosting_absolute_error model shows strong performance with an improved MAE of 11.15 EUR/MWh versus the baseline 24.34 EUR/MWh, and RMSE reduced to 17.31 from 39.64. Fair-value prices for the day-ahead DE-LU market are:  
- Base: €78.93/MWh  
- Peak: €82.11/MWh  
- Offpeak: €75.75/MWh  
Hourly range spans €61.79 to €89.76/MWh.

**2. DA-to-Curve Positioning**  
Current broker marks (front week) are:  
- Base: €86.14/MWh  
- Peak: €88.86/MWh  

The model fair values are significantly below these marks:  
- Base is short by €7.21/MWh  
- Peak is short by €6.74/MWh  

This suggests a bearish prompt view relative to the curve, indicating potential downside risk or overvaluation in current market prices.

**3. View Invalidation Criteria**  
The short prompt positioning should be reconsidered if any of the following occur:  
- Load, wind, or solar forecast revisions shift residual load by more than 2 GW.  
- Prompt curve broker marks move beyond ±€5/MWh threshold before trade execution.  
- Model errors materially widen beyond validation MAE, especially during scarcity or negative-price hours.  
- New information on fuel, carbon costs, outages, or interconnector status alters marginal plant economics after data pull.

Monitor these factors closely to validate or adjust the trading stance.
