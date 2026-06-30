"""Slack notification service for urgent alerts."""
import logging
from typing import Optional, Dict, List
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from app.core.config import settings
from app.models.feedback import Feedback
from app.models.theme import Theme

logger = logging.getLogger(__name__)


class SlackService:
    """Service for sending Slack notifications.

    Sends urgent feedback alerts and clustering summaries to configured channels.
    """

    def __init__(self):
        self.client = None
        if settings.slack_bot_token:
            self.client = WebClient(token=settings.slack_bot_token)
        else:
            logger.warning("Slack bot token not configured, notifications disabled")

    def is_enabled(self) -> bool:
        """Check if Slack integration is enabled."""
        return self.client is not None and bool(settings.slack_channel_urgent)

    async def send_urgent_feedback_alert(self, feedback: Feedback) -> bool:
        """Send alert for urgent/critical feedback.

        Args:
            feedback: Feedback item to alert about

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_enabled():
            logger.info("Slack not enabled, skipping alert")
            return False

        try:
            # Build Slack message blocks
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 Urgent Feedback: {feedback.title}",
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Classification:*\n{feedback.classification or 'Unknown'}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Sentiment:*\n{feedback.sentiment or 'Unknown'}"
                        },
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Content:*\n{feedback.content[:500]}..."
                    }
                },
            ]

            # Add customer info if available
            if feedback.customer_email or feedback.customer_name:
                customer_text = feedback.customer_name or feedback.customer_email or "Unknown"
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Customer: {customer_text} | Received: {feedback.created_at.strftime('%Y-%m-%d %H:%M UTC')}"
                        }
                    ]
                })

            # Add HubSpot link if available
            if feedback.hubspot_ticket_id:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"<https://app.hubspot.com/contacts/tickets/{feedback.hubspot_ticket_id}|View in HubSpot>"
                    }
                })

            # Send message
            response = self.client.chat_postMessage(
                channel=settings.slack_channel_urgent,
                blocks=blocks,
                text=f"Urgent Feedback: {feedback.title}",  # Fallback text
            )

            logger.info(f"Sent urgent alert for feedback {feedback.id} to Slack")
            return True

        except SlackApiError as e:
            logger.error(f"Failed to send Slack alert: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Slack alert: {e}", exc_info=True)
            return False

    async def send_clustering_summary(
        self,
        themes_created: int,
        themes_updated: int,
        themes_deactivated: int,
        top_themes: Optional[List[Theme]] = None,
    ) -> bool:
        """Send weekly clustering summary.

        Args:
            themes_created: Number of new themes created
            themes_updated: Number of existing themes updated
            themes_deactivated: Number of themes deactivated
            top_themes: Optional list of top themes to highlight

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_enabled():
            logger.info("Slack not enabled, skipping clustering summary")
            return False

        try:
            # Build summary message
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 Weekly Clustering Summary",
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*New Themes:*\n{themes_created}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Updated Themes:*\n{themes_updated}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Deactivated Themes:*\n{themes_deactivated}"
                        },
                    ]
                },
            ]

            # Add top themes if provided
            if top_themes:
                theme_text = "\n".join([
                    f"• *{theme.name_en}* — {theme.customer_count} customers, "
                    f"{theme.item_count} feedback items, trend: {theme.trend.value}"
                    for theme in top_themes[:5]
                ])
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Top Themes:*\n{theme_text}"
                    }
                })

            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
                    }
                ]
            })

            # Send message
            response = self.client.chat_postMessage(
                channel=settings.slack_channel_urgent,
                blocks=blocks,
                text="Weekly Clustering Summary",  # Fallback text
            )

            logger.info("Sent clustering summary to Slack")
            return True

        except SlackApiError as e:
            logger.error(f"Failed to send clustering summary: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending clustering summary: {e}", exc_info=True)
            return False

    async def send_bet_notification(
        self,
        bet_title: str,
        theme_name: str,
        customer_count: int,
        feedback_count: int,
    ) -> bool:
        """Send notification about newly generated product bet.

        Args:
            bet_title: Product bet title
            theme_name: Associated theme name
            customer_count: Estimated affected customers
            feedback_count: Number of supporting feedback items

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_enabled():
            logger.info("Slack not enabled, skipping bet notification")
            return False

        try:
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"💡 New Product Bet Generated",
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{bet_title}*"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Theme:*\n{theme_name}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Impact:*\n{customer_count} customers"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Evidence:*\n{feedback_count} feedback items"
                        },
                    ]
                },
            ]

            response = self.client.chat_postMessage(
                channel=settings.slack_channel_urgent,
                blocks=blocks,
                text=f"New Product Bet: {bet_title}",
            )

            logger.info(f"Sent bet notification to Slack: {bet_title}")
            return True

        except SlackApiError as e:
            logger.error(f"Failed to send bet notification: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending bet notification: {e}", exc_info=True)
            return False

    async def send_custom_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[List[Dict]] = None,
    ) -> bool:
        """Send custom message to specified channel.

        Args:
            channel: Slack channel ID or name
            text: Message text (fallback)
            blocks: Optional Slack Block Kit blocks

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.client:
            logger.info("Slack not enabled, skipping custom message")
            return False

        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=text,
                blocks=blocks,
            )

            logger.info(f"Sent custom message to Slack channel {channel}")
            return True

        except SlackApiError as e:
            logger.error(f"Failed to send custom message: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending custom message: {e}", exc_info=True)
            return False
