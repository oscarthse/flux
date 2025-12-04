# Flux Simulation Engine: Research-Grade Specification & Audit

## 1. Expanded Assumption Table

| ID | Domain | Type | Scope | Assumption | Mathematical Form / Logic | Realism (1-5) | Issues / Risks | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **A01** | Demand | Structural | Per-Hour | Arrivals follow a Poisson process. | `Nt ~ Poisson(λt)` | 3 | Real traffic is "bursty" (buses, post-cinema). | **Negative Binomial** `NB(r, p)` to model overdispersion. |
| **A02** | Demand | Parametric | Global | Party size is fixed distribution (30% size 1, 40% size 2...). | `P(S=k) = {0.3, 0.4, ...}` | 2 | Ignores context (Lunch vs Dinner, Wkday vs Wkend). | Conditional `P(S | DayPart, DayOfWeek)`. |
| **A03** | Demand | Structural | Per-Order | "Menu del Día" logic is hardcoded (70% chance on weekday lunch). | `P(Menu \| Lunch, Wkday) = 0.7` | 3 | Static content. Real menus rotate. | **Menu Rotation Engine** with daily variations. |
| **A04** | Capacity | Simplifying | Per-Hour | Capacity is a soft cap on arrivals. | `Nt = min(Poisson, MaxCapacity)` | 1 | **CRITICAL**: Ignores duration. 100 people arriving at 1pm block tables for 2pm. | **Stateful Table Manager** (Little's Law: `L = λW`). |
| **A05** | Inventory | Simplifying | Per-Item | Spoilage is flat 5% of *total* stock if shelf life <= 3 days. | `Waste_t = Stock_t * 0.05` | 1 | **CRITICAL**: Fresh stock doesn't spoil. | **FIFO Batch Tracking** with explicit expiration dates. |
| **A06** | Inventory | Structural | Per-Item | Reordering is purely reactive to Par Level. | `If Stock < Threshold, order Par - Stock` | 3 | Ignores lead-time variability and demand forecast. | **(s, S) Policy** or **Newsvendor** with safety stock. |
| **A07** | Staffing | Simplifying | Daily | Staffing is calculated as a daily aggregate (8hr shifts). | `Staff = ceil(Covers / Ratio)` | 1 | Hides peak-hour bottlenecks. | **Shift-Based Scheduling** (Lunch/Dinner) + Role constraints. |
| **A08** | Weather | Parametric | Daily | Weather is random daily draw (80% Sunny). | `P(Sunny)=0.8` | 2 | No autocorrelation. Rain clusters. | **Markov Chain** `P(Wt | Wt-1)`. |
| **A09** | Pricing | Simplifying | Global | Prices are static. | `Price_t = Price_{t-1}` | 3 | Misses dynamic pricing/Happy Hour. | Time-of-day price modifiers. |
| **A10** | Operations | Parametric | Per-Table | Service time (duration) is fixed or uniform. | `Duration = Constant` | 2 | Real dining time is right-skewed. | **Lognormal Distribution** `LN(μ, σ)` for duration. |
| **A11** | Operations | Structural | Per-Order | Kitchen throughput is infinite. | `PrepTime = 0` | 1 | Kitchens are bottlenecks. | **M/M/c Queue** or max `Items/Hour` cap. |
| **A12** | Heterogeneity | Structural | Global | All restaurants share same parameters. | `Params_r = Params_global` | 1 | "Fine Dining" != "Fast Casual". | **Archetypes** (Casual, Fine, Bar) with distinct param sets. |
| **A13** | Demand | Structural | Daily | Seasonality is non-existent. | `λ_month = Constant` | 2 | Summer/Winter variance is huge. | **Sinusoidal Seasonality** `λ_t * (1 + A*sin(ωt))`. |
| **A14** | Demand | Structural | Daily | Events are binary (Holiday/None). | `Event = {0, 1}` | 2 | Events vary (Concert vs Marathon vs Bank Holiday). | **Event Taxonomy** with specific demand/party-size modifiers. |
| **A15** | Financials | Parametric | Per-Order | Ticket size is sum of menu items. | `Ticket = Σ Prices` | 4 | Accurate but misses "upsell" logic. | **Upsell Probability** model (Coffee/Dessert add-on). |
| **A16** | Inventory | Structural | Per-Item | Recipes are static and deterministic. | `Usage = Recipe * Qty` | 4 | Real usage varies (over-portioning, spills). | **Yield Variance** `Usage ~ N(Recipe, σ_waste)`. |
| **A17** | Inventory | Structural | Per-Delivery | Deliveries arrive exactly on time. | `LeadTime = Constant` | 2 | Suppliers are late. | **Stochastic Lead Time** `LT ~ Poisson(λ)`. |
| **A18** | Operations | Structural | Per-Table | Tables are fungible (any size fits any party). | `Capacity = TotalSeats` | 2 | 2 people can't sit at a full 4-top. | **Bin Packing** logic for tables (2-top, 4-top, etc.). |
| **A19** | Demand | Structural | Per-Channel | All orders are Dine-In. | `Channel = DineIn` | 2 | Delivery/Takeaway is 20-40% of revenue. | **Channel Split** `P(Delivery)` with distinct menus/pricing. |
| **A20** | Staffing | Structural | Per-Hour | Staff productivity is constant. | `Rate = Constant` | 2 | Fatigue/Rush stress affects speed. | **Productivity Curve** (inverted U-shape vs load). |
| **A21** | Demand | Structural | Per-Hour | No balking/reneging. | `Queue = Infinite` | 2 | People leave if line is long. | **Balking Function** `P(Leave | QueueLen)`. |
| **A22** | Financials | Structural | Global | COGS is static. | `Cost = Constant` | 3 | Ingredient prices fluctuate. | **Commodity Price Shock** model. |
| **A23** | Operations | Structural | Per-Day | No "Turn" logic (flipping tables). | Implicit | 2 | Turning tables is a key KPI. | Explicit **Turn Time** (cleaning/reset duration). |
| **A24** | Demand | Structural | Per-Item | Menu items are independent. | `P(A & B) = P(A)P(B)` | 3 | Wine pairs with Steak. | **Association Rules** / Correlation Matrix for ordering. |
| **A25** | Weather | Structural | Per-Channel | Weather affects total demand uniformly. | `λ_new = λ * factor` | 2 | Rain kills Terrace, boosts Delivery. | **Channel-Specific Weather Elasticity**. |
| **A26** | Staffing | Structural | Per-Role | Roles are interchangeable? (Implied). | `Staff = Total` | 2 | Chefs can't wait tables. | **Role-Based Constraints** (Kitchen vs FOH). |
| **A27** | Inventory | Structural | Per-Item | Stockouts result in lost sale of item only. | `Rev -= ItemPrice` | 3 | Real: Guest leaves or substitutes. | **Substitution Logic** `P(Sub | Stockout)`. |
| **A28** | Financials | Structural | Global | No VAT/Tax modeling. | `Rev = Gross` | 3 | Net vs Gross is vital for P&L. | **Tax Layer** (10% food, 21% alc in Spain). |
| **A29** | Operations | Structural | Per-Day | Opening hours are rigid. | `Open = Constant` | 3 | Kitchen closes before restaurant. | **Last Call** logic (kitchen closes 30m early). |
| **A30** | Demand | Structural | Global | No marketing/promo effects. | `λ = Base` | 3 | Promos drive volume but lower margin. | **Campaign Manager** (Spend -> λ boost). |
| **A31** | Inventory | Structural | Per-Item | No minimum order quantities (MOQ). | `Order = ExactNeeded` | 2 | Suppliers sell in cases/pallets. | **MOQ / Pack Size** constraints. |
| **A32** | Heterogeneity | Parametric | Global | Location is generic "Barcelona". | `Loc = BCN` | 2 | Beach vs City Center vs Suburb. | **Geo-Spatial Modifiers** (Tourist vs Residential). |
| **A33** | Staffing | Parametric | Per-Hour | Wages are flat hourly. | `Cost = Rate * Hrs` | 3 | Overtime? Night shift premium? | **Overtime Multiplier** (>40hrs/wk). |
| **A34** | Operations | Structural | Per-Group | Payment is instant. | `PayTime = 0` | 3 | Splitting bills takes time. | **Payment Duration** added to Table Turn. |
| **A35** | Demand | Structural | Per-Day | Weekday/Weekend is binary. | `Profile = {Wkday, Wkend}` | 3 | Friday night != Sunday night. | **7-Day Demand Profile**. |
| **A36** | Inventory | Structural | Per-Item | No "Prep" stage. | `Raw -> Sold` | 2 | Potatoes must be peeled/chopped. | **WIP Inventory** (Mise en place). |
| **A37** | Demand | Structural | Per-Hour | No "Pacing" (Kitchen throttling). | `Order -> Kitchen` | 3 | FOH throttles seating to save kitchen. | **Seating Rhythm** constraints. |
| **A38** | Financials | Structural | Global | Tips not modeled. | `Income = Rev` | 3 | Staff retention depends on tips. | **Tip Model** (% of Rev). |
| **A39** | Operations | Structural | Per-Item | Equipment constraints ignored. | `Infinite Oven` | 2 | Only X pizzas fit in oven. | **Equipment Resource** constraints. |
| **A40** | Demand | Structural | Global | Reputation is static. | `λ = Constant` | 3 | Bad service -> Lower future demand. | **Reputation Feedback Loop**. |

## 2. Deep-Dive Narrative

### A. Demand & Traffic: The "Pulse" of the Restaurant
**Current State**: The model uses a Poisson process with a simple weekday/weekend split.
**Critique**: Real demand is **overdispersed** (Negative Binomial) and highly context-dependent. A "Tuesday Lunch" in a business district is totally different from a "Tuesday Lunch" in a residential area. The current model misses **seasonality** (August in Barcelona is dead for business lunch, huge for tourism) and **event shocks** (Mobile World Congress).
**Improvement**:
1.  **Negative Binomial Arrivals**: $N_t \sim NB(r, p)$ to allow for "clumped" arrivals.
2.  **7-Day Profiles**: Distinct curves for Mon, Tue-Thu, Fri, Sat, Sun.
3.  **Event Layer**: A calendar of events (Concert, Match, Holiday) that applies multipliers to $\lambda$ *and* shifts party size distributions (e.g., Football Match = larger groups, more beer).

### B. Operations: Capacity & Throughput
**Current State**: Capacity is a "soft cap" on arrivals. Kitchen is infinite.
**Critique**: This is the biggest realism gap. A restaurant is a system of **queues**. Tables are a resource held for a duration $D$. If you fill up at 13:30 with people staying 90 mins, you have 0 capacity at 14:00, regardless of the arrival rate. The Kitchen is also a bottleneck; infinite throughput implies instant food, which is impossible.
**Improvement**:
1.  **Stateful Table Manager**: Track `Table(id, capacity, state, release_time)`.
2.  **Service Duration**: Sampled from LogNormal($\mu=90m, \sigma=15m$).
3.  **Kitchen Throttling**: Simple `MaxItemsPerHour` constraint. If backlog > Threshold, increase service time (food takes longer) or stop seating (balking).

### C. Inventory: The Flow of Goods
**Current State**: Flat 5% daily spoilage (mathematically wrong) and reactive reordering.
**Critique**: Ingredients have a lifecycle. They arrive (Batch A), sit in storage, get prepped (Mise en place), and are cooked. Spoilage is a function of **time-since-arrival**, not a daily tax. Reactive reordering ensures stockouts because it ignores **lead time** (time between order and delivery).
**Improvement**:
1.  **FIFO Batching**: `Stock = [Batch(qty=10, exp=Jan5), Batch(qty=20, exp=Jan8)]`. Consume from Jan5 first.
2.  **Stochastic Lead Times**: Delivery takes $L$ days, where $L \sim Poisson(1)$ + MinDays.
3.  **Yield Loss**: 1kg of raw potatoes != 1kg of fries. Model `Yield %` (e.g., 85% yield).

### D. Staffing & Labor
**Current State**: Daily aggregate counts.
**Critique**: Labor is the highest controllable cost. Daily averages hide the critical decisions: "Do I cut the 2nd waiter at 15:00 or 16:00?".
**Improvement**:
1.  **Shift Logic**: Define shifts (e.g., `Lunch: 11:00-17:00`, `Dinner: 19:00-01:00`).
2.  **Role Constraints**: Chefs cook, Servers serve. Ratios ($Covers/Staff$) should be calculated *per hour*.

### E. Heterogeneity: Not All Restaurants Are Equal
**Current State**: One generic "Barcelona" restaurant.
**Critique**: A simulation engine needs to generate *diverse* data. A "Tapas Bar" has high turnover, low ticket, high alcohol. A "Fine Dining" spot has low turnover, high ticket, high service needs.
**Improvement**:
1.  **Archetypes**: Define config classes `TapasBar`, `FineDining`, `FastCasual`.
2.  **Parameter Sampling**: When generating a new restaurant, sample its base parameters (e.g., `AvgTurnTime ~ N(ArchetypeMean, σ)`) so no two are identical.

## 3. Revised Model Spec (Engineering-Ready)

### Core Entities & Variables

```python
@dataclass
class RestaurantConfig:
    archetype: str # "Tapas", "FineDining", "Casual"
    base_turn_time: int # minutes
    seat_capacity: int
    table_mix: Dict[int, int] # {2: 10, 4: 5, 6: 2} (Size: Count)
    menu_complexity: float # Multiplier for kitchen load
    price_point: float # Multiplier for base prices

@dataclass
class Batch:
    id: str
    ingredient_id: int
    quantity: float
    received_date: date
    expiration_date: date
    cost: float

@dataclass
class TableState:
    id: int
    seats: int
    is_occupied: bool
    release_time: datetime
```

### Engine Logic (Pseudo-Code)

#### 1. Demand Engine (Hourly)
```python
def get_arrivals(date, hour, config, events):
    # 1. Base Rate
    dow = date.weekday()
    base_lambda = config.demand_profile[dow][hour]

    # 2. Modifiers
    weather_factor = get_weather_elasticity(config.archetype, weather.current)
    event_factor = events.get_impact(date)
    seasonality = get_seasonality(date)

    final_lambda = base_lambda * weather_factor * event_factor * seasonality

    # 3. Stochastic Generation (Negative Binomial)
    # r (dispersion) varies by archetype (Bars are burstier than Fine Dining)
    r = config.burstiness
    p = r / (r + final_lambda)
    count = np.random.negative_binomial(r, p)

    return count
```

#### 2. Table Manager (Stateful)
```python
class TableManager:
    def try_seat(self, party_size, current_time):
        # 1. Check Capacity
        available_tables = [t for t in self.tables if not t.is_occupied]

        # 2. Bin Packing (Best Fit)
        # Find smallest table that fits party_size
        candidates = [t for t in available_tables if t.seats >= party_size]
        if not candidates:
            return False # Lost Sale (Balking)

        selected_table = min(candidates, key=lambda t: t.seats)

        # 3. Determine Duration (LogNormal)
        mu = np.log(self.config.base_turn_time)
        sigma = 0.2 # Standard variance
        duration = np.random.lognormal(mu, sigma)

        # 4. Update State
        selected_table.is_occupied = True
        selected_table.release_time = current_time + timedelta(minutes=duration)
        return True

    def update_state(self, current_time):
        for t in self.tables:
            if t.is_occupied and current_time >= t.release_time:
                t.is_occupied = False # Table Turn
```

#### 3. Inventory Engine (FIFO)
```python
class InventoryManager:
    def deduct_stock(self, ingredient_id, amount):
        batches = sorted(self.stock[ingredient_id], key=lambda b: b.expiration_date)
        remaining_needed = amount

        for batch in batches:
            if batch.quantity >= remaining_needed:
                batch.quantity -= remaining_needed
                return
            else:
                remaining_needed -= batch.quantity
                batch.quantity = 0
                # Remove empty batch

        if remaining_needed > 0:
            record_stockout(ingredient_id, remaining_needed)

    def check_spoilage(self, current_date):
        for batch in all_batches:
            if batch.expiration_date < current_date:
                record_waste(batch)
                remove_batch(batch)
```

## 4. Validation & Testing Framework

### A. Unit Tests (Logic Verification)
*   **FIFO Enforcement**: Create 2 batches (Old, New). Deduct stock. Assert Old is reduced first.
*   **Expiration**: Set batch exp date to Today. Run `check_spoilage`. Assert batch is moved to Waste log.
*   **Table Locking**: Seat a table for 90 mins. Try to seat again at T+10m. Assert Failure. Try at T+91m. Assert Success.
*   **Recipe Scaling**: Order 10 items. Assert inventory deduction = 10 * Recipe * Yield_Loss.

### B. Statistical Tests (Distribution Sanity)
*   **Arrival Tails**: Run 1000 simulation days. Plot histogram of hourly arrivals. Verify it matches NegBinomial shape (fatter tails than Poisson).
*   **Service Times**: Verify distribution of `release_time - start_time` fits LogNormal.
*   **Waste %**: Run 30 days. Calculate `TotalWaste / TotalStock`. Should be ~1-3% for efficient places, higher for perishables. NOT flat 5%.

### C. Scenario Tests (Stress Testing)
*   **"The Monsoon"**: Force `Weather=Rain` for 7 days.
    *   *Expectation*: Demand drops (Terrace closed), Revenue drops, Perishable waste spikes (overstocked).
*   **"The Festival"**: Force `Event=Festival` (2x demand).
    *   *Expectation*: Revenue caps at `MaxCapacity` (tables full). Lost Sales spike. Kitchen load hits max.
*   **"Supply Shock"**: Force `LeadTime=5 days` (vs normal 1).
    *   *Expectation*: Stockouts on fast-moving items. Revenue drop due to "86'd" items.

### D. Calibration Roadmap
1.  **POS Data Ingestion**: Once real data exists, fit `λ_hour` and `TicketSize` distributions directly.
2.  **Lead Time Analysis**: Analyze supplier invoices to model `LeadTime` distribution.
3.  **Waste Audit**: Use physical inventory logs to tune `Yield` and `Spoilage` parameters.

## 5. Missing Data for Calibration
To move from "Plausible" to "Calibrated", we need:
1.  **Hourly Sales Logs**: To fit Negative Binomial parameters ($r, p$).
2.  **Table Occupancy Logs**: (Start Time, End Time) to fit Service Duration distributions.
3.  **Waste Logs**: To calibrate real spoilage rates vs theoretical shelf life.
4.  **Supplier Invoices**: To measure actual delivery lead time variability.
