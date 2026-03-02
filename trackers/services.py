from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Max, Min, Q
from django.utils import timezone

from .models import PriceObservation, PricePrediction, ProductVariant


class PriceIntelligence:
    """Non-ML scoring system for price intelligence.

    Produces a buy score (0-100), recommendation, confidence level,
    and plain-English explanation based on price history analysis.
    """

    MIN_OBSERVATIONS_FOR_PREDICTION = 5

    @classmethod
    def get_stats(cls, variant: ProductVariant) -> dict:
        """Calculate price statistics for a variant."""
        observations = variant.observations.exclude(price__isnull=True).order_by('recorded_at')

        if not observations.exists():
            return {
                'current_price': variant.current_price,
                'starting_price': None,
                'lowest_price': None,
                'highest_price': None,
                'average_price': None,
                'total_reduction': None,
                'percentage_change': None,
                'last_price_change': None,
                'price_change_count': 0,
                'observation_count': 0,
            }

        first_obs = observations.first()
        last_obs = observations.last()

        stats = observations.aggregate(
            lowest=Min('price'),
            highest=Max('price'),
            average=Avg('price'),
        )

        current = last_obs.price
        starting = first_obs.price
        lowest = stats['lowest']
        highest = stats['highest']
        average = stats['average']

        total_reduction = starting - current if starting and current else None
        percentage_change = ((current - starting) / starting * 100) if starting and current else None

        # Count price changes
        prev_price = None
        change_count = 0
        last_change_at = None
        for obs in observations:
            if prev_price is not None and obs.price != prev_price:
                change_count += 1
                last_change_at = obs.recorded_at
            prev_price = obs.price

        return {
            'current_price': current,
            'starting_price': starting,
            'lowest_price': lowest,
            'highest_price': highest,
            'average_price': average,
            'total_reduction': total_reduction,
            'percentage_change': percentage_change,
            'last_price_change': last_change_at,
            'price_change_count': change_count,
            'observation_count': observations.count(),
        }

    @classmethod
    def classify_price(cls, stats: dict) -> str:
        """Classify the current price relative to history."""
        current = stats['current_price']
        average = stats['average_price']
        lowest = stats['lowest_price']

        if not current or not average:
            return 'Insufficient data'

        if lowest and current == lowest:
            return 'Excellent price'

        pct_below_avg = ((average - current) / average) * 100

        if pct_below_avg > 15:
            return 'Excellent price'
        elif pct_below_avg > 5:
            return 'Good price'
        elif pct_below_avg > -5:
            return 'Typical price'
        elif pct_below_avg > -15:
            return 'Above average'
        else:
            return 'Expensive compared with its recorded history'

    @classmethod
    def generate_prediction(cls, variant: ProductVariant) -> PricePrediction | None:
        """Generate a price prediction using the scoring system."""
        stats = cls.get_stats(variant)

        if stats['observation_count'] < cls.MIN_OBSERVATIONS_FOR_PREDICTION:
            return None

        scores = cls._calculate_scores(stats, variant)
        buy_score = scores['buy_score']

        if buy_score >= 70:
            recommended_action = 'Good time to buy'
            direction = PricePrediction.DIRECTION_DOWN
            probability = Decimal('65')
        elif buy_score >= 50:
            recommended_action = 'Consider buying'
            direction = PricePrediction.DIRECTION_STABLE
            probability = Decimal('50')
        elif buy_score >= 30:
            recommended_action = 'Consider waiting'
            direction = PricePrediction.DIRECTION_UP
            probability = Decimal('40')
        else:
            recommended_action = 'Wait for a better price'
            direction = PricePrediction.DIRECTION_UP
            probability = Decimal('25')

        confidence = cls._determine_confidence(stats)

        explanation = cls._generate_explanation(stats, scores)

        prediction = PricePrediction.objects.create(
            product_variant=variant,
            prediction_type='scoring',
            predicted_direction=direction,
            probability=probability,
            confidence=confidence,
            recommended_action=recommended_action,
            buy_score=buy_score,
            explanation=explanation,
            model_version='scoring-v1',
        )

        return prediction

    @classmethod
    def _calculate_scores(cls, stats: dict, variant: ProductVariant) -> dict:
        """Calculate individual scoring components."""
        current = stats['current_price']
        average = stats['average_price']
        lowest = stats['lowest_price']
        starting = stats['starting_price']
        change_count = stats['price_change_count']

        scores = {}

        # Score 1: Current vs average (0-25)
        if current and average and average > 0:
            pct_below = float(((average - current) / average) * 100)
            scores['vs_average'] = min(25, max(0, (pct_below / 15) * 25))
        else:
            scores['vs_average'] = 12.5

        # Score 2: Current vs minimum (0-25)
        if current and lowest and lowest > 0:
            pct_above_min = float(((current - lowest) / lowest) * 100)
            scores['vs_minimum'] = min(25, max(0, 25 - (pct_above_min / 10) * 25))
        else:
            scores['vs_minimum'] = 12.5

        # Score 3: Frequency of reductions (0-15)
        if change_count > 0:
            scores['reduction_freq'] = min(15, (change_count / 5) * 15)
        else:
            scores['reduction_freq'] = 0

        # Score 4: Days since last change (0-15)
        last_change = stats['last_price_change']
        if last_change:
            days_since = (timezone.now() - last_change).days
            if days_since > 14:
                scores['days_since'] = 12
            elif days_since > 7:
                scores['days_since'] = 8
            elif days_since > 3:
                scores['days_since'] = 5
            else:
                scores['days_since'] = 2
        else:
            scores['days_since'] = 7

        # Score 5: Size of recent movements (0-10)
        if starting and current:
            total_pct = abs(float(((current - starting) / starting) * 100))
            if total_pct > 20:
                scores['movement'] = 10
            elif total_pct > 10:
                scores['movement'] = 7
            elif total_pct > 5:
                scores['movement'] = 4
            else:
                scores['movement'] = 2
        else:
            scores['movement'] = 5

        # Score 6: On sale (original price exists and differs) (0-10)
        obs = variant.observations.exclude(price__isnull=True).exclude(original_price__isnull=True).last()
        if obs and obs.original_price and obs.price and obs.original_price > obs.price:
            scores['on_sale'] = 10
        else:
            scores['on_sale'] = 0

        buy_score = int(sum(scores.values()))
        scores['buy_score'] = buy_score
        return scores

    @classmethod
    def _determine_confidence(cls, stats: dict) -> str:
        obs_count = stats['observation_count']
        if obs_count >= 20:
            return PricePrediction.CONFIDENCE_HIGH
        elif obs_count >= 10:
            return PricePrediction.CONFIDENCE_MEDIUM
        else:
            return PricePrediction.CONFIDENCE_LOW

    @classmethod
    def _generate_explanation(cls, stats: dict, scores: dict) -> str:
        current = stats['current_price']
        average = stats['average_price']
        change_count = stats['price_change_count']

        parts = []

        if current and average and average > 0:
            pct = float(((average - current) / average) * 100)
            if pct > 0:
                parts.append(
                    f'This product is currently {pct:.0f}% below its average recorded price.'
                )
            elif pct < 0:
                parts.append(
                    f'This product is currently {abs(pct):.0f}% above its average recorded price.'
                )

        if change_count >= 2:
            recent_obs = list(stats.get('recent_observations', []))
            parts.append(
                f'The price has changed {change_count} times during the tracking period.'
            )

        if scores.get('on_sale', 0) > 0:
            parts.append('The product appears to be on sale.')

        if not parts:
            parts.append(
                'Tracking has started. A prediction will appear after enough '
                'price observations have been collected.'
            )

        return ' '.join(parts)
