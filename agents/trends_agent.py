"""
Google Trends Agent for MIRS (Medical Intelligence Report System) — Phase 4

This agent is responsible for:
- Fetching search interest over time for medical topics via Google Trends
- Retrieving related queries and rising topics
- Computing trend slope (growth rate) for the Perception Score
- Structuring results for storage in the social_data table

DEFENSIVE DESIGN PRINCIPLES (same as PubMed agent):
- Never returns None for guaranteed fields (uses empty list/dict)
- Validates all data access
- Logs warnings for missing or unexpected data
- Never crashes on malformed input or network issues
- Provides fallbacks for all operations

Uses pytrends (unofficial Google Trends API) — no authentication required.

Author: Michele D. Pierri — Phase 4
"""

import time
import json
import traceback
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False


class TrendsAgent:
    """
    Agent for querying Google Trends with defensive error handling.

    Retrieves:
    - Interest over time (weekly or monthly data points)
    - Related queries (top and rising)
    - Interest by region (country-level)

    All methods return structured dicts/lists, never raise on recoverable
    errors. Warnings are accumulated and can be inspected afterwards.

    Usage:
        agent = TrendsAgent()
        result = agent.fetch_all(topic="aortic dissection")
        print(result['interest_over_time'])
        print(result['related_queries'])
        print(result['trend_slope'])
    """

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 5.0  # seconds between retries (Google rate-limits aggressively)
    REQUEST_DELAY = 1.0  # seconds between sequential requests

    def __init__(self, language: str = "", timezone: int = 0):
        """
        Initialize the Google Trends Agent.

        Args:
            language: Language for Trends results (default: "" = no bias, worldwide)
            timezone: Timezone offset in minutes from UTC (default: 0 = UTC)
        """
        self.language = language
        self.timezone = timezone
        self.warnings: List[Dict] = []

        if not PYTRENDS_AVAILABLE:
            self._log_warning(
                "INIT",
                "pytrends not installed. Run: pip install pytrends"
            )
            self.pytrends = None
        else:
            self.pytrends = TrendReq(
                hl=self.language,
                tz=self.timezone,
                retries=self.MAX_RETRIES,
                backoff_factor=1.0,
            )

        print("Google Trends Agent initialized (DEFENSIVE MODE)")

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def fetch_all(
        self,
        topic: str,
        timeframe: str = "today 5-y",
        geo: str = "",
    ) -> Dict:
        """
        Fetch all Google Trends data for a topic in a single call.

        This is the main entry point. It returns a comprehensive dict
        with interest over time, related queries, trend slope, and
        regional interest.

        Args:
            topic: Medical topic to query (e.g., "aortic dissection")
            timeframe: Timeframe string for pytrends.
                       Examples: "today 5-y", "today 12-m", "2020-01-01 2025-01-01"
            geo: Geographic filter (empty = worldwide, "US" = United States,
                 "IT" = Italy, etc.)

        Returns:
            dict with keys:
                topic (str): Original query
                timeframe (str): Timeframe used
                geo (str): Geographic filter used
                interest_over_time (list[dict]): Time series data points
                    Each: {'date': 'YYYY-MM-DD', 'value': int (0-100)}
                related_queries_top (list[dict]): Top related queries
                    Each: {'query': str, 'value': int}
                related_queries_rising (list[dict]): Rising queries
                    Each: {'query': str, 'value': str (e.g., "Breakout", "+250%")}
                interest_by_region (list[dict]): Country-level interest
                    Each: {'region': str, 'value': int}
                trend_slope (float): Linear regression slope of interest
                    Positive = growing, negative = declining, 0 = stable
                trend_direction (str): "rising", "declining", "stable"
                data_points_count (int): Number of time-series data points
                peak_value (int): Maximum interest value (0-100)
                peak_date (str): Date of peak interest
                current_value (int): Most recent data point value
                fetched_at (str): ISO timestamp of data retrieval
                warnings (list): Warnings logged during fetch
        """
        result = {
            'topic': topic,
            'timeframe': timeframe,
            'geo': geo,
            'interest_over_time': [],
            'related_queries_top': [],
            'related_queries_rising': [],
            'interest_by_region': [],
            'trend_slope': 0.0,
            'trend_direction': 'stable',
            'data_points_count': 0,
            'peak_value': 0,
            'peak_date': '',
            'current_value': 0,
            'fetched_at': datetime.now().isoformat(),
            'warnings': [],
        }

        if not PYTRENDS_AVAILABLE or self.pytrends is None:
            self._log_warning(topic, "pytrends not available — returning empty results")
            result['warnings'] = [w['message'] for w in self.warnings]
            return result

        # 1. Interest over time
        if not self._build_payload(topic, timeframe, geo):
            result['warnings'] = [w['message'] for w in self.warnings]
            return result

        iot_data = self._get_interest_over_time(topic)
        result['interest_over_time'] = iot_data

        if iot_data:
            result['data_points_count'] = len(iot_data)

            # Peak
            peak_item = max(iot_data, key=lambda x: x['value'])
            result['peak_value'] = peak_item['value']
            result['peak_date'] = peak_item['date']

            # Current (most recent data point)
            result['current_value'] = iot_data[-1]['value']

            # Slope
            slope, direction = self._compute_slope(iot_data)
            result['trend_slope'] = slope
            result['trend_direction'] = direction

        time.sleep(self.REQUEST_DELAY)

        # 2. Related queries (rebuild payload — pytrends requires it)
        self._build_payload(topic, timeframe, geo)
        top_q, rising_q = self._get_related_queries(topic)
        result['related_queries_top'] = top_q
        result['related_queries_rising'] = rising_q

        time.sleep(self.REQUEST_DELAY)

        # 3. Interest by region (rebuild payload again)
        self._build_payload(topic, timeframe, geo)
        result['interest_by_region'] = self._get_interest_by_region(topic)

        # Attach warnings
        result['warnings'] = [w['message'] for w in self.warnings]

        print(f"✓ Google Trends fetch complete for '{topic}'")
        print(f"  Data points: {result['data_points_count']}")
        print(f"  Trend: {result['trend_direction']} (slope={result['trend_slope']:.4f})")
        print(f"  Peak: {result['peak_value']}/100 on {result['peak_date']}")
        print(f"  Related queries: {len(top_q)} top, {len(rising_q)} rising")

        return result

    def get_interest_over_time(
        self,
        topic: str,
        timeframe: str = "today 5-y",
        geo: str = "",
    ) -> List[Dict]:
        """
        Fetch only the interest-over-time data (convenience method).

        Args:
            topic: Medical topic to query
            timeframe: Time range string
            geo: Geographic filter

        Returns:
            list[dict]: Time series data points
                Each: {'date': 'YYYY-MM-DD', 'value': int (0-100)}
        """
        if not PYTRENDS_AVAILABLE or self.pytrends is None:
            return []

        if not self._build_payload(topic, timeframe, geo):
            return []

        return self._get_interest_over_time(topic)

    def get_related_queries(
        self,
        topic: str,
        timeframe: str = "today 5-y",
        geo: str = "",
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Fetch only related queries (convenience method).

        Returns:
            Tuple of (top_queries, rising_queries)
        """
        if not PYTRENDS_AVAILABLE or self.pytrends is None:
            return [], []

        if not self._build_payload(topic, timeframe, geo):
            return [], []

        return self._get_related_queries(topic)

    # ──────────────────────────────────────────────────────────────────
    # Internal Methods
    # ──────────────────────────────────────────────────────────────────

    def _build_payload(self, topic: str, timeframe: str, geo: str) -> bool:
        """
        Build the pytrends payload. Must be called before any data fetch.

        Returns:
            bool: True if payload was built successfully
        """
        try:
            self.pytrends.build_payload(
                kw_list=[topic],
                timeframe=timeframe,
                geo=geo,
            )
            return True
        except Exception as e:
            self._log_warning(
                topic,
                f"Failed to build payload: {str(e)}"
            )
            return False

    def _get_interest_over_time(self, topic: str) -> List[Dict]:
        """
        Fetch interest over time with retry logic.

        Returns list of {'date': str, 'value': int} dicts.
        Google normalizes values to 0-100 where 100 = peak popularity.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                df = self.pytrends.interest_over_time()

                if df is None or df.empty:
                    self._log_warning(topic, "Interest over time: no data returned")
                    return []

                # Drop the 'isPartial' column if present
                if 'isPartial' in df.columns:
                    df = df.drop(columns=['isPartial'])

                # The DataFrame has the topic as column name
                # and DatetimeIndex as index
                col_name = topic if topic in df.columns else df.columns[0]

                data_points = []
                for date_idx, row in df.iterrows():
                    data_points.append({
                        'date': date_idx.strftime('%Y-%m-%d'),
                        'value': int(row[col_name]),
                    })

                return data_points

            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    wait = self.RETRY_DELAY * (attempt + 1)
                    print(f"  ⚠ Attempt {attempt + 1} failed, retrying in {wait}s: {e}")
                    time.sleep(wait)
                else:
                    self._log_warning(
                        topic,
                        f"Interest over time failed after {self.MAX_RETRIES} attempts: {str(e)}"
                    )

        return []

    def _get_related_queries(self, topic: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Fetch related queries (top and rising).

        Returns:
            Tuple of (top_queries, rising_queries)
            top: list of {'query': str, 'value': int} — value is relative score 0-100
            rising: list of {'query': str, 'value': str} — value is growth % or "Breakout"
        """
        try:
            related = self.pytrends.related_queries()

            if not related or topic not in related:
                # Try first key if topic key doesn't match exactly
                if related:
                    first_key = list(related.keys())[0]
                    topic_data = related[first_key]
                else:
                    self._log_warning(topic, "Related queries: no data returned")
                    return [], []
            else:
                topic_data = related[topic]

            top_queries = []
            rising_queries = []

            # Parse top queries
            top_df = topic_data.get('top')
            if top_df is not None and not top_df.empty:
                for _, row in top_df.iterrows():
                    top_queries.append({
                        'query': str(row.get('query', '')),
                        'value': int(row.get('value', 0)),
                    })

            # Parse rising queries
            rising_df = topic_data.get('rising')
            if rising_df is not None and not rising_df.empty:
                for _, row in rising_df.iterrows():
                    rising_queries.append({
                        'query': str(row.get('query', '')),
                        'value': str(row.get('value', '')),
                    })

            return top_queries, rising_queries

        except Exception as e:
            self._log_warning(topic, f"Related queries error: {str(e)}")
            return [], []

    # Countries with population under ~1 million — excluded from region chart
    # because Google Trends normalizes by search volume relative to population,
    # making micro-states appear disproportionately high for niche queries.
    MICRO_STATES = {
        "Grenada", "St. Vincent & Grenadines", "Barbados", "Antigua & Barbuda",
        "Dominica", "St. Kitts & Nevis", "St. Lucia", "Seychelles",
        "Maldives", "Malta", "Iceland", "Guam", "Bermuda", "Aruba",
        "Cayman Islands", "Turks & Caicos Islands", "British Virgin Islands",
        "U.S. Virgin Islands", "American Samoa", "Northern Mariana Islands",
        "Palau", "Nauru", "Tuvalu", "Marshall Islands", "San Marino",
        "Liechtenstein", "Monaco", "Andorra", "Macao", "Gibraltar",
        "Falkland Islands", "Montserrat", "Saint Helena", "Anguilla",
        "Wallis & Futuna", "Saint Pierre & Miquelon", "Tokelau", "Niue",
        "Cook Islands", "Vatican City", "Fiji", "Bahamas", "Bhutan",
        "Central African Republic", "Guyana", "Suriname", "Brunei",
        "Cabo Verde", "Comoros", "Djibouti", "Equatorial Guinea",
        "Eswatini", "Gabon", "Gambia", "Guinea-Bissau", "Kiribati",
        "Lesotho", "Micronesia", "Montenegro", "Samoa", "São Tomé & Príncipe",
        "Solomon Islands", "Timor-Leste", "Tonga", "Trinidad & Tobago",
        "Vanuatu", "Palestine", "Jamaica", "Cyprus", "Luxembourg",
        "Mauritius", "Réunion", "Martinique", "Guadeloupe", "French Guiana",
        "New Caledonia", "French Polynesia", "Curaçao", "Sint Maarten",
        "Belize", "Botswana",
    }

    def _get_interest_by_region(self, topic: str) -> List[Dict]:
        """
        Fetch interest by region (country-level).

        Uses inc_low_vol=True to include European and smaller countries.
        Filters out micro-states (population < ~1M) whose normalized scores
        are disproportionately high for specialized queries.

        Returns:
            list of {'region': str, 'value': int} sorted by value descending
        """
        try:
            df = self.pytrends.interest_by_region(
                resolution='COUNTRY',
                inc_low_vol=True,
                inc_geo_code=False,
            )

            if df is None or df.empty:
                self._log_warning(topic, "Interest by region: no data returned")
                return []

            col_name = topic if topic in df.columns else df.columns[0]

            regions = []
            for region_name, row in df.iterrows():
                value = int(row[col_name])
                if value > 0 and str(region_name) not in self.MICRO_STATES:
                    regions.append({
                        'region': str(region_name),
                        'value': value,
                    })

            # Sort by value descending
            regions.sort(key=lambda x: x['value'], reverse=True)

            return regions

        except Exception as e:
            self._log_warning(topic, f"Interest by region error: {str(e)}")
            return []

    # ──────────────────────────────────────────────────────────────────
    # Trend Slope Computation
    # ──────────────────────────────────────────────────────────────────

    def _compute_slope(
        self,
        data_points: List[Dict],
        recent_months: int = 6,
    ) -> Tuple[float, str]:
        """
        Compute the linear regression slope of interest over time.

        Uses the most recent N months of data for the slope calculation,
        as this is more relevant for trend analysis than the full 5-year
        window. The Perception Score uses this slope for the "trend growth"
        component (25% weight).

        Args:
            data_points: List of {'date': str, 'value': int} dicts
            recent_months: Number of recent months to analyze (default 6)

        Returns:
            Tuple of (slope, direction_label)
            slope: Float, normalized per week. Positive = growing.
            direction_label: "rising", "declining", or "stable"
        """
        if not data_points or len(data_points) < 4:
            return 0.0, "stable"

        # Filter to recent N months
        try:
            cutoff_date = datetime.now() - timedelta(days=recent_months * 30)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d')
            recent = [dp for dp in data_points if dp['date'] >= cutoff_str]
        except Exception:
            recent = data_points[-26:]  # Fallback: last ~6 months of weekly data

        if len(recent) < 4:
            recent = data_points[-min(len(data_points), 26):]

        # Simple linear regression: y = mx + b
        # x = index (0, 1, 2, ...), y = value
        n = len(recent)
        values = [dp['value'] for dp in recent]

        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0, "stable"

        slope = numerator / denominator

        # Determine direction based on slope magnitude
        # Threshold: ±0.5 points per week is considered meaningful
        if slope > 0.5:
            direction = "rising"
        elif slope < -0.5:
            direction = "declining"
        else:
            direction = "stable"

        return round(slope, 4), direction

    # ──────────────────────────────────────────────────────────────────
    # Data Conversion for DB Storage
    # ──────────────────────────────────────────────────────────────────

    def to_social_data_records(
        self,
        trends_result: Dict,
        query_id: int,
    ) -> List[Dict]:
        """
        Convert a fetch_all() result into records ready for the
        social_data database table.

        Each interest-over-time data point becomes a row, plus
        a summary row with metadata (related queries, slope, etc.).

        Args:
            trends_result: Dict returned by fetch_all()
            query_id: FK to the queries table

        Returns:
            List of dicts matching SocialData fields:
                query_id, source, source_id, content, title, url,
                sentiment, engagement, posted_at, extra_data
        """
        records = []

        # Summary record with full metadata
        summary_content = json.dumps({
            'interest_over_time': trends_result.get('interest_over_time', []),
            'related_queries_top': trends_result.get('related_queries_top', []),
            'related_queries_rising': trends_result.get('related_queries_rising', []),
            'interest_by_region': trends_result.get('interest_by_region', []),
        }, ensure_ascii=False)

        records.append({
            'query_id': query_id,
            'source': 'google_trends',
            'source_id': f"trends_summary_{trends_result.get('topic', '')}",
            'content': summary_content,
            'title': f"Google Trends: {trends_result.get('topic', '')}",
            'url': f"https://trends.google.com/trends/explore?q={trends_result.get('topic', '').replace(' ', '+')}",
            'sentiment': None,  # Trends data has no sentiment
            'engagement': trends_result.get('peak_value', 0),
            'posted_at': datetime.now(),
            'extra_data': json.dumps({
                'timeframe': trends_result.get('timeframe', ''),
                'geo': trends_result.get('geo', ''),
                'trend_slope': trends_result.get('trend_slope', 0),
                'trend_direction': trends_result.get('trend_direction', 'stable'),
                'data_points_count': trends_result.get('data_points_count', 0),
                'peak_date': trends_result.get('peak_date', ''),
                'current_value': trends_result.get('current_value', 0),
            }, ensure_ascii=False),
        })

        return records

    # ──────────────────────────────────────────────────────────────────
    # Warning System (same pattern as PubMed agent)
    # ──────────────────────────────────────────────────────────────────

    def _log_warning(self, context: str, message: str):
        """Log a warning about missing or problematic data."""
        warning_msg = f"[Trends: {context}] {message}"
        print(f"  ⚠ {warning_msg}")
        self.warnings.append({
            'context': context,
            'message': message,
            'timestamp': datetime.now().isoformat(),
        })

    def get_warnings(self) -> List[Dict]:
        """Get all warnings logged during operations."""
        return self.warnings

    def clear_warnings(self):
        """Clear all accumulated warnings."""
        self.warnings = []

    def print_warning_summary(self):
        """Print a summary of all warnings."""
        if not self.warnings:
            print("\n✓ No warnings — all Trends data fetched successfully!")
            return

        print(f"\n{'=' * 60}")
        print(f"WARNING SUMMARY: {len(self.warnings)} total warnings")
        print(f"{'=' * 60}")
        for w in self.warnings:
            print(f"  [{w['context']}] {w['message']}")


# ── Standalone test ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Google Trends Agent — Standalone Test")
    print("=" * 60)

    agent = TrendsAgent()

    if not PYTRENDS_AVAILABLE:
        print("\n✗ pytrends is not installed.")
        print("  Install with: pip install pytrends")
        sys.exit(1)

    # Test with a cardiothoracic surgery topic
    topic = "aortic dissection"
    print(f"\nFetching trends for: '{topic}'")
    print("-" * 40)

    result = agent.fetch_all(topic=topic, timeframe="today 5-y")

    print(f"\n{'=' * 60}")
    print(f"RESULTS")
    print(f"{'=' * 60}")
    print(f"  Topic: {result['topic']}")
    print(f"  Timeframe: {result['timeframe']}")
    print(f"  Data points: {result['data_points_count']}")
    print(f"  Trend: {result['trend_direction']} (slope={result['trend_slope']})")
    print(f"  Peak: {result['peak_value']}/100 on {result['peak_date']}")
    print(f"  Current: {result['current_value']}/100")

    if result['related_queries_top']:
        print(f"\n  Top related queries:")
        for q in result['related_queries_top'][:5]:
            print(f"    - {q['query']} ({q['value']})")

    if result['related_queries_rising']:
        print(f"\n  Rising queries:")
        for q in result['related_queries_rising'][:5]:
            print(f"    - {q['query']} ({q['value']})")

    if result['interest_by_region']:
        print(f"\n  Top regions:")
        for r in result['interest_by_region'][:10]:
            print(f"    - {r['region']}: {r['value']}")

    # Test DB record conversion
    db_records = agent.to_social_data_records(result, query_id=1)
    print(f"\n  DB records generated: {len(db_records)}")

    agent.print_warning_summary()
