"""Synthetic Transaction Data Pipeline and Behavioral Fraud Engine.

Generates realistic transaction streams where transactions are not independent:
users have established historical behaviors (amount range, diurnal active hours,
home and travel locations, preferred merchants, known devices, and frequency).
Fraud scenarios deliberately alter these behavioral baselines.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
import random
from typing import Any, Sequence
from uuid import UUID, uuid4


# Reference locations with approximate coordinates (lat, lon) for distance calculations
LOCATIONS: dict[str, tuple[float, float, str]] = {
    "New York, US": (40.7128, -74.0060, "US"),
    "San Francisco, US": (37.7749, -122.4194, "US"),
    "Chicago, US": (41.8781, -87.6298, "US"),
    "Austin, US": (30.2672, -97.7431, "US"),
    "London, UK": (51.5074, -0.1278, "GB"),
    "Berlin, DE": (52.5200, 13.4050, "DE"),
    "Paris, FR": (48.8566, 2.3522, "FR"),
    "Mumbai, IN": (19.0760, 72.8777, "IN"),
    "Bengaluru, IN": (12.9716, 77.5946, "IN"),
    "Singapore, SG": (1.3521, 103.8198, "SG"),
    "Tokyo, JP": (35.6762, 139.6503, "JP"),
    "Sydney, AU": (-33.8688, 151.2093, "AU"),
}

MERCHANT_CATEGORIES = [
    "groceries",
    "retail",
    "food_dining",
    "travel",
    "electronics",
    "digital_goods",
    "entertainment",
    "luxury",
    "crypto",
    "gambling",
]

PAYMENT_METHODS = ["credit_card", "debit_card", "upi", "bank_transfer", "apple_pay", "google_pay"]

DEVICE_PLATFORMS = ["iOS", "Android", "macOS", "Windows", "Linux"]


def haversine_distance_km(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    """Calculate the great-circle distance between two points in kilometers."""
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return 6371.0 * c


@dataclass
class DeviceProfile:
    device_id: UUID
    fingerprint: str
    platform: str
    is_compromised: bool = False


@dataclass
class MerchantProfile:
    merchant_id: UUID
    external_id: str
    name: str
    category: str
    country_code: str
    risk_level: str = "LOW"
    typical_min_amount: float = 5.0
    typical_max_amount: float = 500.0


@dataclass
class UserProfile:
    user_id: UUID
    email: str
    display_name: str
    account_created_at: datetime
    # Historical behavioral parameters
    typical_amount_mean: float
    typical_amount_std: float
    min_amount: float
    max_amount: float
    active_hours_start: int  # e.g., 7 (7 AM)
    active_hours_end: int  # e.g., 23 (11 PM)
    home_location: str
    travel_locations: list[str]
    devices: list[DeviceProfile]
    primary_device_id: UUID
    ip_subnet: str
    known_ips: list[str]
    preferred_merchants: list[UUID]
    preferred_categories: list[str]
    preferred_payment_methods: list[str]
    daily_frequency: float  # average transactions per day
    is_dormant: bool = False
    last_transaction_id: UUID | None = None
    last_transaction_time: datetime | None = None
    last_transaction_location: str | None = None


@dataclass
class TransactionRecord:
    transaction_id: UUID
    user_id: UUID
    timestamp: datetime
    amount: Decimal
    currency: str
    merchant_id: UUID
    merchant_category: str
    device_id: UUID
    ip_address: str
    location: str
    account_age: int  # account age in days
    payment_method: str
    transaction_status: str
    previous_transaction_id: UUID | None
    is_fraud: bool
    fraud_scenario: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["transaction_id"] = str(self.transaction_id)
        result["user_id"] = str(self.user_id)
        result["merchant_id"] = str(self.merchant_id)
        result["device_id"] = str(self.device_id)
        result["previous_transaction_id"] = (
            str(self.previous_transaction_id) if self.previous_transaction_id else None
        )
        result["timestamp"] = self.timestamp.isoformat()
        result["amount"] = float(self.amount)
        return result


class SyntheticTransactionGenerator:
    """Reproducible, behavioral synthetic transaction pipeline."""

    def __init__(
        self,
        seed: int = 42,
        currency: str = "USD",
        start_date: datetime | None = None,
        duration_days: int = 60,
    ) -> None:
        self.seed = seed
        self.currency = currency
        self.rng = random.Random(seed)
        self.start_date = start_date or (datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
        self.end_date = self.start_date + timedelta(days=duration_days)
        self.merchants: list[MerchantProfile] = []
        self.users: list[UserProfile] = []
        self._shared_ring_device: DeviceProfile | None = None
        self._shared_ring_ip: str | None = None

    def initialize_world(
        self,
        num_users: int = 50,
        num_merchants: int = 20,
    ) -> tuple[list[UserProfile], list[MerchantProfile]]:
        """Instantiate user profiles and merchant directory with consistent behavioral traits."""
        self._init_merchants(num_merchants)
        self._init_users(num_users)
        return self.users, self.merchants

    def _init_merchants(self, count: int) -> None:
        merchant_names = [
            ("FreshMart Grocery", "groceries", "US", 10.0, 150.0),
            ("GreenValley Organics", "groceries", "US", 15.0, 180.0),
            ("City Metro Mart", "groceries", "GB", 8.0, 120.0),
            ("Apex Electronics", "electronics", "US", 50.0, 2500.0),
            ("Volt Tech Store", "electronics", "IN", 40.0, 1800.0),
            ("Silicon Direct", "electronics", "US", 100.0, 3500.0),
            ("Velvet Couture", "luxury", "FR", 200.0, 5000.0),
            ("Aura Jewelry Co", "luxury", "US", 300.0, 7500.0),
            ("BlueSky Air Travel", "travel", "US", 120.0, 1500.0),
            ("Global Rail & Ferry", "travel", "DE", 20.0, 300.0),
            ("StreamWave Media", "digital_goods", "US", 5.0, 45.0),
            ("CloudByte Hosting", "digital_goods", "US", 10.0, 200.0),
            ("BitVault Gateway", "crypto", "US", 50.0, 10000.0),
            ("CoinSentry Exchange", "crypto", "SG", 100.0, 15000.0),
            ("Golden Crown Casino", "gambling", "GB", 25.0, 2500.0),
            ("LuckySpin Gaming", "gambling", "AU", 10.0, 1000.0),
            ("Corner Bistro & Cafe", "food_dining", "US", 5.0, 60.0),
            ("Artisan Coffee Roasters", "food_dining", "US", 3.0, 25.0),
            ("Urban Streetwear Retail", "retail", "US", 20.0, 250.0),
            ("NextGen Gear", "retail", "DE", 30.0, 400.0),
        ]
        self.merchants = []
        for i in range(count):
            name, cat, ccode, min_amt, max_amt = merchant_names[i % len(merchant_names)]
            ext_id = f"merch_{i + 1:04d}"
            risk_level = "HIGH" if cat in ("crypto", "gambling", "luxury") else "LOW"
            self.merchants.append(
                MerchantProfile(
                    merchant_id=uuid4(),
                    external_id=ext_id,
                    name=f"{name} #{i + 1}" if i >= len(merchant_names) else name,
                    category=cat,
                    country_code=ccode,
                    risk_level=risk_level,
                    typical_min_amount=min_amt,
                    typical_max_amount=max_amt,
                )
            )

    def _init_users(self, count: int) -> None:
        location_keys = list(LOCATIONS.keys())
        self.users = []
        for i in range(count):
            user_id = uuid4()
            home_loc = self.rng.choice(location_keys)
            travel_options = [loc for loc in location_keys if loc != home_loc]
            travel_locs = self.rng.sample(travel_options, k=min(3, len(travel_options)))

            account_age_init_days = self.rng.randint(30, 730)
            account_created = self.start_date - timedelta(days=account_age_init_days)

            # Assign devices
            platform1 = self.rng.choice(["iOS", "Android"])
            dev1 = DeviceProfile(
                device_id=uuid4(),
                fingerprint=f"fp-{user_id.hex[:8]}-mobile-{platform1.lower()}",
                platform=platform1,
            )
            devices = [dev1]
            if self.rng.random() < 0.6:
                platform2 = self.rng.choice(["macOS", "Windows", "Linux"])
                dev2 = DeviceProfile(
                    device_id=uuid4(),
                    fingerprint=f"fp-{user_id.hex[:8]}-desktop-{platform2.lower()}",
                    platform=platform2,
                )
                devices.append(dev2)

            # Assign IP pool
            subnet_prefix = f"198.51.{self.rng.randint(10, 200)}"
            known_ips = [f"{subnet_prefix}.{self.rng.randint(2, 250)}" for _ in range(2)]

            # Normal spending behavior distribution
            # e.g., low-spenders ($25 median), medium ($60), high ($150)
            tier = self.rng.choices(["low", "medium", "high"], weights=[0.55, 0.35, 0.10])[0]
            if tier == "low":
                mean_amt = self.rng.uniform(15.0, 45.0)
                std_amt = mean_amt * 0.35
            elif tier == "medium":
                mean_amt = self.rng.uniform(45.0, 110.0)
                std_amt = mean_amt * 0.40
            else:
                mean_amt = self.rng.uniform(110.0, 300.0)
                std_amt = mean_amt * 0.50

            # Active daily hours (diurnal pattern)
            wake_hour = self.rng.randint(6, 9)
            sleep_hour = self.rng.randint(21, 24)

            # Favorite merchants (typically 3 to 6 preferred merchants)
            preferred_merchants = [m.merchant_id for m in self.rng.sample(self.merchants, k=min(5, len(self.merchants)))]
            preferred_cats = list({m.category for m in self.merchants if m.merchant_id in preferred_merchants})
            preferred_pay = self.rng.sample(PAYMENT_METHODS, k=self.rng.randint(1, 2))

            # Daily frequency
            daily_freq = self.rng.uniform(0.5, 2.5)

            # Occasional dormant users
            is_dormant = (i % 12 == 0)

            user = UserProfile(
                user_id=user_id,
                email=f"user_{i + 1}_{user_id.hex[:6]}@example.com",
                display_name=f"User {i + 1}",
                account_created_at=account_created,
                typical_amount_mean=mean_amt,
                typical_amount_std=std_amt,
                min_amount=max(1.0, mean_amt - 2.5 * std_amt),
                max_amount=mean_amt + 3.5 * std_amt,
                active_hours_start=wake_hour,
                active_hours_end=sleep_hour,
                home_location=home_loc,
                travel_locations=travel_locs,
                devices=devices,
                primary_device_id=dev1.device_id,
                ip_subnet=subnet_prefix,
                known_ips=known_ips,
                preferred_merchants=preferred_merchants,
                preferred_categories=preferred_cats,
                preferred_payment_methods=preferred_pay,
                daily_frequency=daily_freq,
                is_dormant=is_dormant,
            )
            self.users.append(user)

        # Pre-seed a coordinated fraud network device and IP
        self._shared_ring_device = DeviceProfile(
            device_id=uuid4(),
            fingerprint="fp-ring-shared-emulator-v4",
            platform="Android",
            is_compromised=True,
        )
        self._shared_ring_ip = "192.0.2.199"

    def _sample_legitimate_amount(self, user: UserProfile) -> Decimal:
        """Sample an amount from user's normal lognormal distribution."""
        # Convert mean and std into log-normal parameters
        mu = math.log((user.typical_amount_mean ** 2) / math.sqrt(user.typical_amount_mean ** 2 + user.typical_amount_std ** 2))
        sigma = math.sqrt(math.log(1.0 + (user.typical_amount_std ** 2) / (user.typical_amount_mean ** 2)))
        val = self.rng.lognormvariate(mu, sigma)
        val = max(user.min_amount, min(val, user.max_amount * 1.5))
        return Decimal(f"{val:.2f}")

    def _sample_legitimate_time(self, user: UserProfile, day_date: datetime) -> datetime:
        """Sample time strictly within the user's diurnal active waking hours."""
        hour_range = list(range(user.active_hours_start, user.active_hours_end))
        hour = self.rng.choice(hour_range)
        minute = self.rng.randint(0, 59)
        second = self.rng.randint(0, 59)
        return day_date.replace(hour=hour, minute=minute, second=second)

    def _sample_legitimate_location(self, user: UserProfile) -> str:
        """Normal location with occasional scheduled travel."""
        if self.rng.random() < 0.94 or not user.travel_locations:
            return user.home_location
        return self.rng.choice(user.travel_locations)

    def _sample_legitimate_device(self, user: UserProfile) -> DeviceProfile:
        """User uses their primary device ~85% of the time."""
        if self.rng.random() < 0.85 or len(user.devices) == 1:
            return user.devices[0]
        return user.devices[1]

    def _sample_legitimate_merchant(self, user: UserProfile) -> MerchantProfile:
        """Normal merchant selection matching user preferences."""
        if self.rng.random() < 0.80 and user.preferred_merchants:
            m_id = self.rng.choice(user.preferred_merchants)
            m = next((m for m in self.merchants if m.merchant_id == m_id), None)
            if m:
                return m
        # Select low/medium risk merchant
        safe_merchants = [m for m in self.merchants if m.risk_level == "LOW"]
        return self.rng.choice(safe_merchants or self.merchants)

    def _create_transaction_record(
        self,
        user: UserProfile,
        timestamp: datetime,
        amount: Decimal,
        merchant: MerchantProfile,
        device: DeviceProfile,
        ip_address: str,
        location: str,
        payment_method: str,
        transaction_status: str = "completed",
        is_fraud: bool = False,
        fraud_scenario: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TransactionRecord:
        """Build transaction record maintaining sequential history chaining."""
        account_age_days = max(0, (timestamp.date() - user.account_created_at.date()).days)
        tx_id = uuid4()
        prev_id = user.last_transaction_id

        record = TransactionRecord(
            transaction_id=tx_id,
            user_id=user.user_id,
            timestamp=timestamp,
            amount=amount,
            currency=self.currency,
            merchant_id=merchant.merchant_id,
            merchant_category=merchant.category,
            device_id=device.device_id,
            ip_address=ip_address,
            location=location,
            account_age=account_age_days,
            payment_method=payment_method,
            transaction_status=transaction_status,
            previous_transaction_id=prev_id,
            is_fraud=is_fraud,
            fraud_scenario=fraud_scenario,
            metadata=metadata or {},
        )

        # Update historical user state
        user.last_transaction_id = tx_id
        user.last_transaction_time = timestamp
        user.last_transaction_location = location
        return record

    def generate_legitimate_stream(self, max_transactions_per_user: int = 40) -> list[TransactionRecord]:
        """Simulate natural historical activity for all users."""
        transactions: list[TransactionRecord] = []
        days_total = max(1, (self.end_date - self.start_date).days)

        for user in self.users:
            if user.is_dormant:
                continue
            # Schedule transactions chronologically across the window
            num_tx = int(user.daily_frequency * days_total)
            num_tx = min(num_tx, max_transactions_per_user)
            if num_tx <= 0:
                num_tx = 1

            # Distribute across days
            assigned_days = sorted(self.rng.sample(range(days_total), k=min(num_tx, days_total)))
            for day_offset in assigned_days:
                day_date = self.start_date + timedelta(days=day_offset)
                tx_time = self._sample_legitimate_time(user, day_date)
                amount = self._sample_legitimate_amount(user)
                merchant = self._sample_legitimate_merchant(user)
                device = self._sample_legitimate_device(user)
                ip = self.rng.choice(user.known_ips)
                location = self._sample_legitimate_location(user)
                payment_method = self.rng.choice(user.preferred_payment_methods)

                tx = self._create_transaction_record(
                    user=user,
                    timestamp=tx_time,
                    amount=amount,
                    merchant=merchant,
                    device=device,
                    ip_address=ip,
                    location=location,
                    payment_method=payment_method,
                    transaction_status="completed",
                    is_fraud=False,
                )
                transactions.append(tx)

        return transactions

    # -------------------------------------------------------------------------
    # 8 Specific Fraud Scenarios
    # -------------------------------------------------------------------------

    def inject_account_takeover(self, user: UserProfile, target_time: datetime) -> list[TransactionRecord]:
        """Scenario 1: Account Takeover (ATO).
        
        Attacker uses an unfamiliar new device, distant/foreign IP, shifts location,
        and conducts a high-value draining transaction.
        """
        alien_device = DeviceProfile(
            device_id=uuid4(),
            fingerprint=f"fp-alien-hijack-{uuid4().hex[:6]}",
            platform="Linux",
            is_compromised=True,
        )
        alien_ip = f"203.0.113.{self.rng.randint(2, 250)}"  # external IP
        distant_location = "London, UK" if "US" in user.home_location else "New York, US"
        high_amount = Decimal(f"{user.typical_amount_mean * self.rng.uniform(8.0, 18.0):.2f}")
        merchant = next((m for m in self.merchants if m.category in ("electronics", "crypto", "luxury")), self.merchants[0])

        tx = self._create_transaction_record(
            user=user,
            timestamp=target_time,
            amount=high_amount,
            merchant=merchant,
            device=alien_device,
            ip_address=alien_ip,
            location=distant_location,
            payment_method=user.preferred_payment_methods[0],
            transaction_status="completed",
            is_fraud=True,
            fraud_scenario="account_takeover",
            metadata={"indicator": "unrecognized_device_and_high_deviation"},
        )
        return [tx]

    def inject_transaction_burst(self, user: UserProfile, target_time: datetime, burst_count: int = 8) -> list[TransactionRecord]:
        """Scenario 2: Transaction Burst (Velocity Spike).
        
        Multiple rapid transactions occurring within minutes, violating the user's
        normal daily Poisson frequency.
        """
        records: list[TransactionRecord] = []
        merchant = next((m for m in self.merchants if m.category in ("digital_goods", "gaming")), self.merchants[0])
        current_time = target_time

        for i in range(burst_count):
            current_time = current_time + timedelta(seconds=self.rng.randint(15, 60))
            amount = Decimal(f"{self.rng.uniform(40.0, 180.0):.2f}")
            tx = self._create_transaction_record(
                user=user,
                timestamp=current_time,
                amount=amount,
                merchant=merchant,
                device=user.devices[0],
                ip_address=user.known_ips[0],
                location=user.home_location,
                payment_method=user.preferred_payment_methods[0],
                transaction_status="completed",
                is_fraud=True,
                fraud_scenario="transaction_burst",
                metadata={"burst_index": i + 1, "velocity_flag": True},
            )
            records.append(tx)
        return records

    def inject_device_takeover(self, user: UserProfile, target_time: datetime) -> list[TransactionRecord]:
        """Scenario 3: Device Takeover.
        
        Legitimate credentials operated from a suspicious device (e.g., rooted Android / emulator)
        generating anomalous transactions.
        """
        emulator_device = DeviceProfile(
            device_id=uuid4(),
            fingerprint=f"fp-emulator-nox-{uuid4().hex[:6]}",
            platform="Android",
            is_compromised=True,
        )
        proxy_ip = f"198.18.{self.rng.randint(10, 90)}.{self.rng.randint(2, 250)}"
        high_amount = Decimal(f"{user.typical_amount_mean * 4.5:.2f}")
        merchant = next((m for m in self.merchants if m.category == "retail"), self.merchants[0])

        tx = self._create_transaction_record(
            user=user,
            timestamp=target_time,
            amount=high_amount,
            merchant=merchant,
            device=emulator_device,
            ip_address=proxy_ip,
            location=user.home_location,
            payment_method=user.preferred_payment_methods[0],
            transaction_status="completed",
            is_fraud=True,
            fraud_scenario="device_takeover",
            metadata={"device_risk": "emulator_detected"},
        )
        return [tx]

    def inject_impossible_travel(self, user: UserProfile, target_time: datetime) -> list[TransactionRecord]:
        """Scenario 4: Impossible Travel (Geo-Velocity).
        
        Consecutive transactions for the same user spaced only minutes apart,
        but located thousands of kilometers away from each other.
        """
        # First transaction: at user's home location
        first_loc = user.home_location
        first_time = target_time
        merchant = self.merchants[0]
        tx1 = self._create_transaction_record(
            user=user,
            timestamp=first_time,
            amount=Decimal("35.00"),
            merchant=merchant,
            device=user.devices[0],
            ip_address=user.known_ips[0],
            location=first_loc,
            payment_method=user.preferred_payment_methods[0],
            transaction_status="completed",
            is_fraud=False,
        )

        # Second transaction: distant continent 20 minutes later
        distant_loc = "Tokyo, JP" if "US" in first_loc else "San Francisco, US"
        coord1 = LOCATIONS[first_loc][:2]
        coord2 = LOCATIONS[distant_loc][:2]
        dist_km = haversine_distance_km(coord1, coord2)
        delta_minutes = 20
        speed_kmh = (dist_km / delta_minutes) * 60.0

        second_time = first_time + timedelta(minutes=delta_minutes)
        foreign_device = DeviceProfile(
            device_id=uuid4(),
            fingerprint=f"fp-remote-{uuid4().hex[:6]}",
            platform="iOS",
        )
        tx2 = self._create_transaction_record(
            user=user,
            timestamp=second_time,
            amount=Decimal(f"{user.typical_amount_mean * 3.0:.2f}"),
            merchant=self.merchants[1],
            device=foreign_device,
            ip_address="192.0.2.77",
            location=distant_loc,
            payment_method=user.preferred_payment_methods[0],
            transaction_status="completed",
            is_fraud=True,
            fraud_scenario="impossible_travel",
            metadata={
                "distance_km": round(dist_km, 1),
                "delta_minutes": delta_minutes,
                "apparent_speed_kmh": round(speed_kmh, 1),
            },
        )
        return [tx1, tx2]

    def inject_merchant_abuse(self, user: UserProfile, target_time: datetime) -> list[TransactionRecord]:
        """Scenario 5: Merchant Abuse.
        
        Abnormal high-value, repeated round-dollar transactions targeted at a
        high-risk or collusive merchant (e.g. gift card / crypto / electronics).
        """
        records: list[TransactionRecord] = []
        target_merchant = next((m for m in self.merchants if m.category in ("crypto", "luxury", "electronics")), self.merchants[0])
        current_time = target_time

        for i in range(3):
            current_time = current_time + timedelta(minutes=self.rng.randint(3, 12))
            round_amount = Decimal(str(self.rng.choice([500, 1000, 1500, 2000])))
            tx = self._create_transaction_record(
                user=user,
                timestamp=current_time,
                amount=round_amount,
                merchant=target_merchant,
                device=user.devices[0],
                ip_address=user.known_ips[0],
                location=user.home_location,
                payment_method=user.preferred_payment_methods[0],
                transaction_status="completed",
                is_fraud=True,
                fraud_scenario="merchant_abuse",
                metadata={"abuse_type": "collusion_round_amount", "attempt": i + 1},
            )
            records.append(tx)
        return records

    def inject_card_testing(self, user: UserProfile, target_time: datetime, test_count: int = 5) -> list[TransactionRecord]:
        """Scenario 6: Card Testing.
        
        Rapid series of micro-amounts ($0.50, $1.00, $2.00) in fast succession
        to verify stolen card validity.
        """
        records: list[TransactionRecord] = []
        merchant = next((m for m in self.merchants if m.category in ("retail", "digital_goods")), self.merchants[0])
        current_time = target_time

        micro_amounts = [Decimal("0.50"), Decimal("1.00"), Decimal("1.75"), Decimal("2.10"), Decimal("0.99")]
        for i in range(test_count):
            current_time = current_time + timedelta(seconds=self.rng.randint(10, 45))
            amount = micro_amounts[i % len(micro_amounts)]
            tx = self._create_transaction_record(
                user=user,
                timestamp=current_time,
                amount=amount,
                merchant=merchant,
                device=DeviceProfile(device_id=uuid4(), fingerprint=f"fp-bot-{uuid4().hex[:6]}", platform="Linux"),
                ip_address=f"198.51.100.{self.rng.randint(100, 250)}",
                location=user.home_location,
                payment_method="credit_card",
                transaction_status="completed" if i < test_count - 1 else "failed",
                is_fraud=True,
                fraud_scenario="card_testing",
                metadata={"test_attempt": i + 1, "micro_charge": True},
            )
            records.append(tx)
        return records

    def inject_coordinated_fraud_network(
        self,
        users_subset: Sequence[UserProfile],
        target_time: datetime,
    ) -> list[TransactionRecord]:
        """Scenario 7: Coordinated Fraud Network (Fraud Ring).
        
        Multiple distinct user accounts secretly sharing the exact same device ID
        and IP address executing synchronized fraudulent orders.
        """
        records: list[TransactionRecord] = []
        target_merchant = next((m for m in self.merchants if m.category in ("electronics", "luxury")), self.merchants[0])
        shared_dev = self._shared_ring_device or DeviceProfile(
            device_id=uuid4(), fingerprint="fp-ring-shared", platform="Android"
        )
        shared_ip = self._shared_ring_ip or "192.0.2.199"
        current_time = target_time

        for idx, user in enumerate(users_subset):
            current_time = current_time + timedelta(minutes=self.rng.randint(2, 8))
            amount = Decimal(f"{self.rng.uniform(650.0, 1400.0):.2f}")
            tx = self._create_transaction_record(
                user=user,
                timestamp=current_time,
                amount=amount,
                merchant=target_merchant,
                device=shared_dev,
                ip_address=shared_ip,
                location=user.home_location,
                payment_method="credit_card",
                transaction_status="completed",
                is_fraud=True,
                fraud_scenario="coordinated_fraud_network",
                metadata={"ring_id": "ring_alpha", "member_index": idx + 1},
            )
            records.append(tx)
        return records

    def inject_sudden_behavioral_change(self, user: UserProfile, target_time: datetime) -> list[TransactionRecord]:
        """Scenario 8: Sudden Behavioral Change.
        
        A dormant or quiet user with low-value daytime grocery pattern suddenly
        executes multiple 10x-20x transactions at 3 AM in high-risk categories.
        """
        night_time = target_time.replace(hour=3, minute=self.rng.randint(10, 50))
        high_risk_merchant = next((m for m in self.merchants if m.category in ("crypto", "luxury")), self.merchants[0])
        massive_amount = Decimal(f"{max(2500.0, user.typical_amount_mean * 25.0):.2f}")

        tx = self._create_transaction_record(
            user=user,
            timestamp=night_time,
            amount=massive_amount,
            merchant=high_risk_merchant,
            device=user.devices[0],
            ip_address=user.known_ips[0],
            location=user.home_location,
            payment_method=user.preferred_payment_methods[0],
            transaction_status="completed",
            is_fraud=True,
            fraud_scenario="sudden_behavioral_change",
            metadata={"hour": night_time.hour, "spending_multiplier": float(massive_amount / Decimal(str(user.typical_amount_mean)))},
        )
        return [tx]

    def generate_complete_dataset(
        self,
        num_users: int = 50,
        num_merchants: int = 20,
        fraud_ratio: float = 0.08,
    ) -> list[TransactionRecord]:
        """Build a complete, chronologically sorted transaction dataset combining
        natural historical activity and all 8 fraud scenarios.
        """
        self.initialize_world(num_users=num_users, num_merchants=num_merchants)
        all_transactions: list[TransactionRecord] = []

        # 1. Generate natural legitimate baseline
        legit_txs = self.generate_legitimate_stream()
        all_transactions.extend(legit_txs)

        # 2. Inject each of the 8 fraud scenarios into the timeline
        days_total = max(3, (self.end_date - self.start_date).days)
        active_users = [u for u in self.users if not u.is_dormant]

        def safe_offset(pct: float) -> int:
            return max(0, min(days_total - 1, int(days_total * pct)))

        if active_users:
            u_len = len(active_users)
            # Scenario 1: Account Takeover
            t1 = self.start_date + timedelta(days=safe_offset(0.35), hours=14)
            all_transactions.extend(self.inject_account_takeover(active_users[0 % u_len], t1))

            # Scenario 2: Transaction Burst
            t2 = self.start_date + timedelta(days=safe_offset(0.20), hours=11)
            all_transactions.extend(self.inject_transaction_burst(active_users[1 % u_len], t2))

            # Scenario 3: Device Takeover
            t3 = self.start_date + timedelta(days=safe_offset(0.45), hours=16)
            all_transactions.extend(self.inject_device_takeover(active_users[2 % u_len], t3))

            # Scenario 4: Impossible Travel
            t4 = self.start_date + timedelta(days=safe_offset(0.55), hours=10)
            all_transactions.extend(self.inject_impossible_travel(active_users[3 % u_len], t4))

            # Scenario 5: Merchant Abuse
            t5 = self.start_date + timedelta(days=safe_offset(0.30), hours=13)
            all_transactions.extend(self.inject_merchant_abuse(active_users[4 % u_len], t5))

            # Scenario 6: Card Testing
            t6 = self.start_date + timedelta(days=safe_offset(0.15), hours=19)
            all_transactions.extend(self.inject_card_testing(active_users[5 % u_len], t6))

            # Scenario 7: Coordinated Fraud Network (shared ring across up to 4 users)
            t7 = self.start_date + timedelta(days=safe_offset(0.70), hours=15)
            ring_users = active_users[6:10] if u_len >= 10 else active_users[:min(4, u_len)]
            all_transactions.extend(self.inject_coordinated_fraud_network(ring_users, t7))

            # Scenario 8: Sudden Behavioral Change
            dormant_or_quiet = next((u for u in self.users if u.is_dormant), active_users[7 % u_len])
            t8 = self.start_date + timedelta(days=safe_offset(0.80))
            all_transactions.extend(self.inject_sudden_behavioral_change(dormant_or_quiet, t8))

        # Sort strictly chronologically
        all_transactions.sort(key=lambda tx: tx.timestamp)

        # Re-link previous_transaction_id sequentially per user in chronological order
        # to ensure historical integrity without forward-referencing or cycle anomalies
        user_history: dict[UUID, UUID] = {}
        for tx in all_transactions:
            tx.previous_transaction_id = user_history.get(tx.user_id)
            user_history[tx.user_id] = tx.transaction_id

        return all_transactions
