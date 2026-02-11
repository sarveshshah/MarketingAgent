# Marketing Campaign Strategy Report

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Campaign Overview

| Aspect | Details |
|--------|---------|
| Campaign Type | {campaign_input.campaign_type} |
| Target Industry | {campaign_input.target_industry} |
| Budget | {campaign_input.budget} |
| Timeline | {campaign_input.timeline} |
| Goals | {campaign_input.goals} |

---

## Data-Driven Insights
### Historical Campaign Analysis
{insights}

### Market Trends
{trends}

---

## Recommended Strategy
### Target Audience
{strategy.target_audience if strategy else 'N/A'}
### Campaign Channels
{strategy.campaign_channels if strategy else 'N/A'}
### Acquisition Cost Estimate
{strategy.acquisition_cost_estimate if strategy else 'N/A'}
### Expected ROI
{strategy.expected_roi if strategy else 'N/A'}

---

## Channel Recommendations
### Primary Channels
{channels.primary_channels if channels else 'N/A'}
### Channel Rationale
{channels.channel_rationale if channels else 'N/A'}
### Expected Reach & Engagement
{channels.expected_reach if channels else 'N/A'}

---

## Budget Optimization Plan
### Channel Breakdown
{budget.channel_breakdown if budget else 'N/A'}
### Timeline Phases
{budget.timeline_phases if budget else 'N/A'}
### Contingency Plan
{budget.contingency_plan if budget else 'N/A'}

---

## Risk Assessment & Mitigation
### Identified Risks
{risks.identified_risks if risks else 'N/A'}
### Mitigation Strategies
{risks.mitigation_strategies if risks else 'N/A'}
### Success Metrics & KPIs
{risks.success_metrics if risks else 'N/A'}    
"""