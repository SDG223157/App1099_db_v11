# app/utils/analysis/news_service.py

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import traceback
from app.utils.config.news_config import NewsConfig
from app.utils.data.news_service import NewsService
from .news_analyzer import NewsAnalyzer
from app.models import NewsArticle, ArticleSymbol  # Add at top
from sqlalchemy import func  # Add this import

class NewsAnalysisService:
    def __init__(self):
        """Initialize the news analysis service"""
        self.logger = logging.getLogger(__name__)
        self.analyzer = NewsAnalyzer("apify_api_ewwcE7264pu0eRgeUBL2RaFk6rmCdy4AaAU9")
        self.db = NewsService()
    def get_news_by_date_range(self, start_date, end_date, symbol=None, page=1, per_page=20):
        try:
            return self.db.get_articles_by_date_range(
                start_date=start_date,
                end_date=end_date,
                symbol=symbol,
                page=page,
                per_page=per_page
            )
        except Exception as e:
            self.logger.error(f"Error getting articles by date range: {str(e)}")
            return [], 0

    def get_sentiment_summary(self, days=7, symbol=None):
        """Get detailed sentiment analysis including daily breakdown"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            articles, total = self.db.get_articles_by_date_range(
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                symbol=symbol
            )
            
            if not articles:
                return {
                    "average_sentiment": 0,
                    "daily_sentiment": {},
                    "highest_day": {"date": None, "value": 0},
                    "lowest_day": {"date": None, "value": 0},
                    "total_articles": 0
                }

            # Group articles by date
            daily_data = {}
            for article in articles:
                date_str = article['published_at'][:10]  # Extract YYYY-MM-DD
                sentiment = article['summary']['ai_sentiment_rating'] or 0
                
                if date_str not in daily_data:
                    daily_data[date_str] = {
                        'total_sentiment': 0,
                        'article_count': 0
                    }
                
                daily_data[date_str]['total_sentiment'] += sentiment
                daily_data[date_str]['article_count'] += 1

            # Calculate daily averages and find extremes
            daily_sentiment = {}
            max_sentiment = -float('inf')
            min_sentiment = float('inf')
            total_sentiment = 0
            total_articles = 0
            
            for date, data in daily_data.items():
                avg = data['total_sentiment'] / data['article_count']
                daily_sentiment[date] = {
                    'average_sentiment': avg,
                    'article_count': data['article_count']
                }
                
                total_sentiment += data['total_sentiment']
                total_articles += data['article_count']
                
                if avg > max_sentiment:
                    max_sentiment = avg
                    max_date = date
                    
                if avg < min_sentiment:
                    min_sentiment = avg
                    min_date = date

            return {
                "average_sentiment": total_sentiment / total_articles if total_articles else 0,
                "daily_sentiment": daily_sentiment,
                "highest_day": {
                    "date": max_date,
                    "value": round(max_sentiment, 1)
                },
                "lowest_day": {
                    "date": min_date,
                    "value": round(min_sentiment, 1)
                },
                "total_articles": total_articles
            }
            
        except Exception as e:
            self.logger.error(f"Error getting sentiment summary: {str(e)}")
            return {
                "average_sentiment": 0,
                "daily_sentiment": {},
                "highest_day": {"date": None, "value": 0},
                "lowest_day": {"date": None, "value": 0},
                "total_articles": 0
            }

    def search_articles(self, keyword=None, symbol=None, start_date=None, 
                       end_date=None, sentiment=None, page=1, per_page=20):
        """
        Search articles (renamed from search_news to match route expectations)
        """
        try:
            return self.db.search_articles(
                keyword=keyword,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                sentiment=sentiment,
                page=page,
                per_page=per_page
            )
        except Exception as e:
            self.logger.error(f"Error searching articles: {str(e)}")
            return [], 0

    def close(self):
        """Clean up resources"""
        try:
            if hasattr(self.db, 'engine'):
                self.db.engine.dispose()
        except Exception as e:
            self.logger.error(f"Error closing resources: {str(e)}")
        
    def fetch_and_analyze_news(self, symbols: List[str], limit: int = 10) -> List[Dict]:
        """
        Fetch news articles from Apify, analyze them, and store in database
        """
        try:
            self.logger.info(f"Starting news fetch for symbols: {symbols}")
            
            if not symbols or not isinstance(symbols, list) or not isinstance(limit, int) or limit <= 0:
                self.logger.error(f"Invalid input parameters: symbols={symbols}, limit={limit}")
                return []

            # 1. Fetch raw news
            raw_articles = self.analyzer.get_news(symbols, limit)
            if not raw_articles:
                return []
            
            # 2. Process and analyze articles
            analyzed_articles = []
            for idx, article in enumerate(raw_articles, 1):
                try:
                    if not article:
                        continue
                        
                    # Analyze article
                    analyzed = self.analyzer.analyze_article(article)
                    if not analyzed or not self._validate_article(analyzed):
                        continue
                    
                    # Save to database
                    article_id = self.db.save_article(analyzed)
                    if article_id:
                        analyzed['id'] = article_id
                        analyzed_articles.append(analyzed)
                    
                except Exception as e:
                    self.logger.error(f"Error processing article {idx}: {str(e)}")
                    continue
            
            return analyzed_articles
            
        except Exception as e:
            self.logger.error(f"Error in fetch_and_analyze_news: {str(e)}")
            return []

    
    # def get_sentiment_summary(
    #     self,
    #     date: str = None,
    #     symbol: str = None,
    #     days: int = 7
    # ) -> Dict:
    #     """
    #     Get sentiment summary statistics
        
    #     Args:
    #         date (str, optional): Specific date for summary
    #         symbol (str, optional): Filter by symbol
    #         days (int): Number of days to analyze if no specific date
            
    #     Returns:
    #         Dict: Sentiment summary statistics
    #     """
    #     try:
    #         if date:
    #             return self.db.get_daily_sentiment_summary(date, symbol)
    #         else:
    #             # Calculate summary for last N days
    #             end_date = datetime.now()
    #             start_date = end_date - timedelta(days=days)
                
    #             articles, _ = self.db.get_articles_by_date_range(
    #                 start_date=start_date.strftime("%Y-%m-%d"),
    #                 end_date=end_date.strftime("%Y-%m-%d"),
    #                 symbol=symbol
    #             )
                
    #             if not articles:
    #                 return {
    #                     "total_articles": 0,
    #                     "sentiment_distribution": {
    #                         "positive": 0,
    #                         "negative": 0,
    #                         "neutral": 0
    #                     },
    #                     "average_sentiment": 0
    #                 }
                
    #             # Calculate statistics
    #             positive = sum(1 for a in articles if a['sentiment_label'] == 'POSITIVE')
    #             negative = sum(1 for a in articles if a['sentiment_label'] == 'NEGATIVE')
    #             neutral = sum(1 for a in articles if a['sentiment_label'] == 'NEUTRAL')
                
    #             return {
    #                 "total_articles": len(articles),
    #                 "sentiment_distribution": {
    #                     "positive": positive,
    #                     "negative": negative,
    #                     "neutral": neutral
    #                 },
    #                 "average_sentiment": sum(a['sentiment_score'] for a in articles) / len(articles)
    #             }
                
    #     except Exception as e:
    #         self.logger.error(f"Error getting sentiment summary: {str(e)}")
    #         return {}

    def get_trending_topics(self, days: int = NewsConfig.TRENDING_DAYS) -> List[Dict]:
        """
        Get trending topics from recent news
        
        Args:
            days (int): Number of days to analyze
            
        Returns:
            List[Dict]: Trending topics with statistics
        """
        try:
            return self.db.get_trending_topics(days)
        except Exception as e:
            self.logger.error(f"Error getting trending topics: {str(e)}")
            return []
    
    def _validate_article(self, article: Dict) -> bool:
        """Validate required article fields"""
        required_fields = ['external_id', 'title', 'published_at']
        return all(article.get(field) for field in required_fields)

    def get_articles_by_date_range(
        self,
        start_date: str,
        end_date: str,
        symbol: str = None,
        page: int = 1,
        per_page: int = 20
    ):
        """Get articles within date range"""
        try:
            return self.db.search_articles(
                start_date=start_date,
                end_date=end_date,
                symbol=symbol,
                page=page,
                per_page=per_page
            )
        except Exception as e:
            self.logger.error(f"Error getting articles by date range: {str(e)}")
            return [], 0

    def search_news(
        self,
        keyword: str = None,
        symbol: str = None,
        start_date: str = None,
        end_date: str = None,
        sentiment: str = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Search news articles with various filters"""
        try:
            return self.db.search_articles(
                keyword=keyword,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                sentiment=sentiment,
                page=page,
                per_page=per_page
            )
        except Exception as e:
            self.logger.error(f"Error searching articles: {str(e)}")
            return [], 0

    def get_article_by_id(self, article_id: int) -> Optional[Dict]:
        """Get article by ID"""
        try:
            return self.db.get_article_by_id(article_id)
        except Exception as e:
            self.logger.error(f"Error getting article by ID: {str(e)}")
            return None

    def get_article_by_external_id(self, external_id: str) -> Optional[Dict]:
        """Get article by external ID"""
        try:
            return self.db.get_article_by_external_id(external_id)
        except Exception as e:
            self.logger.error(f"Error getting article by external ID: {str(e)}")
            return None

    def close(self):
        """Clean up resources"""
        try:
            self.db.close()
        except Exception as e:
            self.logger.error(f"Error closing resources: {str(e)}")

    def get_sentiment_timeseries(self, symbol: str, days: int):
        """Get daily sentiment averages for a specific symbol"""
        # Get the latest article date instead of using current time
        latest_article = self.db.session.query(
            func.max(NewsArticle.published_at)
        ).join(NewsArticle.symbols).filter(
            ArticleSymbol.symbol == symbol.upper()
        ).scalar()

        end_date = latest_article or datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get base query
        query = self.db.session.query(
            func.date(NewsArticle.published_at).label('date'),
            func.avg(NewsArticle.ai_sentiment_rating).label('avg_sentiment'),
            func.count(NewsArticle.id).label('article_count')
        ).join(NewsArticle.symbols).filter(
            ArticleSymbol.symbol == symbol.upper(),
            NewsArticle.published_at >= start_date,
            NewsArticle.published_at <= end_date,
            NewsArticle.ai_sentiment_rating.isnot(None)
        ).group_by('date').order_by('date')

        # Execute query and format results
        results = query.all()
        
        # Create complete date range
        date_dict = {}
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            date_dict[date_str] = {
                'average_sentiment': 0,
                'article_count': 0
            }
            current_date += timedelta(days=1)

        # Fill with actual data
        for date, avg, count in results:
            date_str = date.strftime('%Y-%m-%d')
            date_dict[date_str] = {
                'average_sentiment': round(float(avg), 2) if avg else 0,
                'article_count': count
            }

        return date_dict