# DE-LU Day-Ahead Power Fair-Value Memo – 2025-12-31

**Signal Summary:**  
The hist_gradient_boosting_absolute_error model shows strong performance improvements over the baseline, halving MAE from 24.34 to 12.33 EUR/MWh and reducing RMSE from 39.64 to 21.64 EUR/MWh. The model’s fair-value base price is 79.52 EUR/MWh, with peak at 85.19 EUR/MWh and offpeak at 73.84 EUR/MWh. Hourly fair values range from a low of 59.19 to a high of 94.57 EUR/MWh.

**DA-to-Curve Positioning:**  
- **Base:** The model fair value is 6.62 EUR/MWh below the trailing 7-day front week base curve mark (86.14 EUR/MWh), signaling a short prompt base stance.  
- **Peak:** The peak fair value is 3.67 EUR/MWh below the curve mark (88.86 EUR/MWh), which is within the 5 EUR/MWh threshold, indicating a neutral prompt peak position.

**Invalidation Triggers:**  
This view should be reconsidered if any of the following occur before execution:  
- Day-ahead load, wind, or solar forecast revisions shift residual load by more than 2 GW.  
- Prompt curve broker marks move beyond the 5 EUR/MWh edge threshold.  
- Model errors increase significantly compared to validation MAE, especially during scarcity or negative-price hours.  
- New fuel, carbon, outage, or interconnector information alters marginal plant economics after data pull.

Monitor these factors closely to maintain model reliability and adjust positioning accordingly.
