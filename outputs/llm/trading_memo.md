# DE-LU Day-Ahead Power Fair-Value Memo – 2025-12-31

**Signal Summary:**  
Our improved day-ahead fair-value model for Germany/Luxembourg power shows a significant accuracy gain over the baseline, with MAE reduced from 24.34 to 13.57 EUR/MWh and RMSE from 39.64 to 23.98 EUR/MWh. The model fair values for base and peak are €79.42/MWh and €82.97/MWh respectively. These reflect a conservative estimate compared to actual prices and recent curve marks.

**DA-to-Curve Positioning:**  
- **Base:** Model fair value is €6.72/MWh below the front-week base curve mark (€86.14), signaling a short prompt base stance.  
- **Peak:** Model fair value is €5.88/MWh below the front-week peak curve mark (€88.86), supporting a short prompt peak position.  
The model’s minimum and maximum hourly fair values (€56.08 to €92.04) are also notably below actual observed extremes, indicating potential downside risk in prompt prices.

**Invalidation Triggers:**  
This view should be reconsidered if any of the following occur before execution:  
- Day-ahead load, wind, or solar forecast revisions shift residual load by more than 2 GW.  
- Prompt curve broker marks move beyond the ±€5/MWh edge threshold.  
- Model errors widen materially beyond validation MAE, especially during scarcity or negative-price hours.  
- New fuel, carbon, outage, or interconnector information alters marginal plant economics after data pull.

Monitor these factors closely to validate or adjust the short prompt positions accordingly.
