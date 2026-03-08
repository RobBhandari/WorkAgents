# Engineering Intelligence Observatory

## System Architecture

This document describes the architecture of the **Engineering Intelligence Observatory**.

The platform collects engineering metrics, stores historical data, generates trends,
detects signals, and presents insights through dashboards and APIs.

---

# System Overview

The platform converts raw engineering metrics into leadership-level engineering intelligence.

The data flow is intentionally simple:

Collectors → Historical Data → Trend Pipeline → Signals Engine → API → Dashboards

Each layer has a clearly defined responsibility.

---

# High Level Architecture

```
                 +------------------------+
                 |   External Systems     |
                 |------------------------|
                 | Azure DevOps           |
                 | Security scanners      |
                 | AI usage logs          |
                 +-----------+------------+
                             |
                             v
                    +------------------+
                    |    Collectors    |
                    |------------------|
                    | execution/       |
                    | collectors/      |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    | Historical Data  |
                    |------------------|
                    | .tmp/observatory |
                    | *_history.json   |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    | Trends Pipeline  |
                    |------------------|
                    | calculate trends |
                    | build metrics    |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    |  Signals Engine  |
                    |------------------|
                    | detect signals   |
                    | prioritise risks |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    |        API       |
                    |------------------|
                    | FastAPI service  |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    |     Frontend     |
                    |------------------|
                    | React dashboard  |
                    +------------------+
```

---

# Core Components

## 1. Collectors

Collectors retrieve engineering metrics from external systems.

Examples:

* Azure DevOps
* security scanners
* internal tooling
* AI usage logs

Collectors are located in:

```
execution/collectors/
```

Collectors are responsible for:

* retrieving raw metric data
* transforming it into standard metric format
* appending to historical metric files

Collectors **never perform trend analysis**.

---

# 2. Historical Metrics Store

Historical engineering data is stored locally as JSON time-series files.

Location:

```
.tmp/observatory/
```

Examples:

```
quality_history.json
security_history.json
flo
```
# Command Centre Dashboard

The Engineering Intelligence Observatory is designed to evolve into a
**portfolio-level engineering command centre**.

The dashboard surfaces engineering intelligence rather than raw metrics.

Target layout:

```
┌──────────────────────────────────────────┐
│ Engineering Intelligence Observatory     │
│ Portfolio Health | Signals | Trends      │
└──────────────────────────────────────────┘

┌──────────────┬──────────────┬──────────────┐
│ Health Score │ Key Signals  │ Active Risks │
└──────────────┴──────────────┴──────────────┘

┌──────────────────────────────────────────┐
│ Engineering Trends (last 12 weeks)       │
│ Deployment | Lead Time | Security | Bugs │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ Product Risk Heatmap                     │
└──────────────────────────────────────────┘
```

This layout provides leadership with a clear view of:

• overall engineering health
• important signals and changes
• trend visibility across key metrics
• product-level risk exposure

The dashboard should prioritise **signals and trends over raw metrics**.
