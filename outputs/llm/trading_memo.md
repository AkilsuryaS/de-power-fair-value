# DE-LU Day-Ahead Power Fair-Value Memo – 2025-12-31

**Signal Summary:**  
The hist_gradient_boosting_absolute_error model delivers a robust fair-value estimate for DE-LU day-ahead power prices, significantly improving accuracy with an MAE of 11.15 EUR/MWh versus the baseline 24.34 EUR/MWh. The model fair values stand at 78.93 EUR/MWh (base), 82.11 EUR/MWh (peak), and 75.75 EUR/MWh (offpeak). Hourly fair values range from a low of 61.79 EUR/MWh to a high of 89.76 EUR/MWh.

**DA-to-Curve Positioning:**  
Current prompt curve broker marks for the front week are 86.14 EUR/MWh (base) and 88.86 EUR/MWh (peak). The model fair values are notably lower by 7.21 EUR/MWh (base) and 6.74 EUR/MWh (peak), signaling a short prompt base and peak stance. This suggests the market is pricing power above the model’s fair value, indicating potential downside risk or overvaluation in prompt contracts.

**Invalidation Triggers:**  
This view should be reconsidered if any of the following occur before execution:  
- Day-ahead load, wind, or solar forecast revisions shift residual load by more than 2 GW.  
- Prompt curve broker marks move beyond the 5 EUR/MWh edge threshold.  
- Model errors widen materially beyond the validation MAE, especially during scarcity or negative-price hours.  
- New fuel, carbon, outage, or interconnector developments alter marginal plant economics post data pull.

Monitor these factors closely to validate or adjust the current short prompt positioning.
