"""
PubMed Agent for MIRS (Medical Intelligence Report System) - DEFENSIVE VERSION

This agent is responsible for:
- Searching PubMed database using E-utilities API
- Retrieving article metadata (title, abstract, authors, journal, etc.)
- Parsing and structuring the results with DEFENSIVE handling
- Handling API rate limits and errors
- Logging data quality issues without crashing

DEFENSIVE DESIGN PRINCIPLES:
- Never returns None for guaranteed fields (uses empty string/list)
- Validates all nested dictionary access
- Logs warnings for missing data
- Provides fallbacks for all parsing operations
- Never crashes on malformed input

Uses NCBI Biopython Entrez module for reliable API interaction.
"""

import sys
import os

from Bio import Entrez
import time
import re
from typing import List, Dict, Optional
from datetime import datetime
import config

# Configure Entrez with our credentials
Entrez.email = config.PUBMED_EMAIL
Entrez.api_key = config.PUBMED_API_KEY


class PubMedAgent:
    """
    Agent for querying PubMed database with defensive parsing.
    
    This class encapsulates all PubMed search functionality:
    - ESearch: find PMIDs matching a query
    - EFetch: retrieve full metadata for articles
    - Defensive parsing: handle missing/malformed data gracefully
    - Warning system: track data quality issues
    """
    
    def __init__(self):
        """
        Initialize the PubMed Agent.
        
        Sets up:
        - Request delay for rate limiting
        - Default parameters for searches
        - Warning tracking system
        """
        self.request_delay = config.REQUEST_DELAY
        self.default_max_results = config.DEFAULT_MAX_RESULTS
        self.warnings = []  # Track parsing issues
        
        print(f"PubMed Agent initialized (DEFENSIVE MODE)")
        print(f"  - Rate limit: {1/self.request_delay:.1f} requests/second")
        print(f"  - Default max results: {self.default_max_results}")
    
    
    def search(
        self, 
        query: str, 
        max_results: int = None,
        date_from: str = None,
        date_to: str = None,
        article_types: List[str] = None
    ) -> List[str]:
        """
        Search PubMed and return a list of PMIDs (PubMed IDs).
        
        This uses ESearch E-utility which returns only article IDs.
        The actual article data is retrieved separately with fetch().
        
        Args:
            query (str): Search query in PubMed format 
                        Example: "aortic dissection AND surgery"
            max_results (int, optional): Maximum number of results to return
                                        Defaults to config.DEFAULT_MAX_RESULTS
            date_from (str, optional): Start date in YYYY/MM/DD format
                                      Example: "2020/01/01"
            date_to (str, optional): End date in YYYY/MM/DD format
                                    Example: "2024/12/31"
            article_types (List[str], optional): Filter by article type
                                                Example: ["Clinical Trial", "Meta-Analysis"]
        
        Returns:
            List[str]: List of PMIDs as strings
                      Example: ["38123456", "38123457", ...]
        
        Raises:
            Exception: If API call fails or returns an error
        """
        
        # Use default max_results if not specified
        # None means "fetch all" — use 9999 as PubMed practical limit per request
        if max_results is None:
            max_results = 9999
        
        print(f"\n🔍 Searching PubMed...")
        print(f"  Query: {query}")
        print(f"  Max results: {max_results}")
        
        # Build the search term with optional filters
        search_term = query
        
        # Add date range filter if specified
        if date_from or date_to:
            date_filter = self._build_date_filter(date_from, date_to)
            search_term = f"({search_term}) AND {date_filter}"
            print(f"  Date range: {date_from or 'start'} to {date_to or 'now'}")
        
        # Add article type filter if specified
        if article_types:
            type_filter = " OR ".join([f'"{t}"[Publication Type]' for t in article_types])
            search_term = f"({search_term}) AND ({type_filter})"
            print(f"  Article types: {', '.join(article_types)}")
        
        try:
            # Call NCBI ESearch API
            handle = Entrez.esearch(
                db="pubmed",
                term=search_term,
                retmax=max_results,
                sort="relevance"
            )
            
            # Parse the XML response
            record = Entrez.read(handle)
            handle.close()
            
            # Extract the list of PMIDs from the response
            pmids = record["IdList"]
            
            # Get the total count of matching articles
            total_count = int(record["Count"])
            
            print(f"✓ Found {len(pmids)} articles (total matching: {total_count})")
            
            # Respect rate limits
            time.sleep(self.request_delay)
            
            return pmids
            
        except Exception as e:
            print(f"✗ Error searching PubMed: {str(e)}")
            raise
    
    
    def fetch(self, pmids: List[str]) -> List[Dict]:
        """
        Fetch full article metadata for a list of PMIDs with defensive parsing.
        
        This uses EFetch E-utility which returns complete article data.
        All parsing is defensive - missing data is logged but doesn't crash.
        
        Args:
            pmids (List[str]): List of PubMed IDs to fetch
        
        Returns:
            List[Dict]: List of article dictionaries with structured data
                       All fields are guaranteed to exist (possibly empty)
        """
        
        if not pmids:
            print("⚠ No PMIDs provided to fetch")
            return []
        
        print(f"\n📥 Fetching metadata for {len(pmids)} articles...")
        
        articles = []
        batch_size = config.DEFAULT_RETMAX
        
        # Process PMIDs in batches
        for i in range(0, len(pmids), batch_size):
            batch_pmids = pmids[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(pmids) + batch_size - 1) // batch_size
            
            print(f"  Batch {batch_num}/{total_batches}: fetching {len(batch_pmids)} articles...")
            
            try:
                # Call NCBI EFetch API
                handle = Entrez.efetch(
                    db="pubmed",
                    id=batch_pmids,
                    rettype="abstract",
                    retmode="xml"
                )
                
                # Parse the XML response
                records = Entrez.read(handle)
                handle.close()
                
                # Extract and structure data with defensive parsing
                for record in records['PubmedArticle']:
                    article_data = self._parse_article(record)
                    articles.append(article_data)
                
                print(f"    ✓ Parsed {len(batch_pmids)} articles")
                
                # Respect rate limits between batches
                time.sleep(self.request_delay)
                
            except Exception as e:
                print(f"    ✗ Error fetching batch: {str(e)}")
                # Continue with next batch even if one fails
                continue
        
        print(f"✓ Total articles fetched: {len(articles)}")
        
        # Report warnings if any
        if self.warnings:
            print(f"⚠ {len(self.warnings)} warnings logged during parsing")
        
        return articles
    
    
    def count(
        self,
        query: str,
        date_from: str = None,
        date_to: str = None,
        article_types: List[str] = None,
    ) -> int:
        """
        Count matching articles on PubMed WITHOUT fetching any data.

        Uses ESearch with retmax=0 to get only the total count.
        This is fast and costs no bandwidth.

        Args:
            query: Search query string
            date_from: Optional start date YYYY/MM/DD
            date_to: Optional end date YYYY/MM/DD
            article_types: Optional article type filters

        Returns:
            int: Total number of matching articles on PubMed
        """
        search_term = query

        if date_from or date_to:
            date_filter = self._build_date_filter(date_from, date_to)
            search_term = f"({search_term}) AND {date_filter}"

        if article_types:
            type_filter = " OR ".join(
                [f'"{t}"[Publication Type]' for t in article_types]
            )
            search_term = f"({search_term}) AND ({type_filter})"

        try:
            handle = Entrez.esearch(
                db="pubmed",
                term=search_term,
                retmax=0,
            )
            record = Entrez.read(handle)
            handle.close()
            time.sleep(self.request_delay)
            return int(record.get("Count", 0))
        except Exception as e:
            print(f"✗ Count failed: {e}")
            return -1

    def search_and_fetch(
        self, 
        query: str, 
        max_results: int = None,
        date_from: str = None,
        date_to: str = None,
        article_types: List[str] = None
    ) -> List[Dict]:
        """
        Convenience method that combines search() and fetch() in one call.
        
        Args:
            query (str): Search query
            max_results (int, optional): Maximum results. If None, fetches ALL
                                        matching articles (no artificial limit).
            date_from (str, optional): Start date YYYY/MM/DD
            date_to (str, optional): End date YYYY/MM/DD
            article_types (List[str], optional): Article type filters
        
        Returns:
            List[Dict]: List of complete article data dictionaries
        """
        
        # Clear warnings from previous runs
        self.clear_warnings()
        
        # Step 1: Search for PMIDs
        pmids = self.search(
            query=query,
            max_results=max_results,
            date_from=date_from,
            date_to=date_to,
            article_types=article_types
        )
        
        # Step 2: Fetch full metadata
        if pmids:
            articles = self.fetch(pmids)
            return articles
        else:
            print("⚠ No articles found")
            return []
    
    
    def _parse_article(self, record: Dict) -> Dict:
        """
        Parse a single PubMed article with comprehensive defensive handling.
        
        GUARANTEES:
        - Never returns None for any field
        - All string fields are strings (possibly empty)
        - All list fields are lists (possibly empty)
        - Logs warnings for missing critical data
        - Never crashes on malformed input
        
        Args:
            record: Raw PubMed article record from Entrez
        
        Returns:
            Dict: Structured article with guaranteed field types
        """
        
        try:
            # Extract nested structures safely
            medline = record.get('MedlineCitation', {})
            article = medline.get('Article', {})
            
            # PMID - should always exist, but be defensive
            pmid = str(medline.get('PMID', 'UNKNOWN'))
            if pmid == 'UNKNOWN':
                self._log_warning('UNKNOWN', "Article without PMID encountered")
            
            # Title - should always exist
            title = article.get('ArticleTitle', '')
            if not title:
                self._log_warning(pmid, "Article has no title")
                title = "No title available"
            
            # Abstract - use defensive extraction
            abstract = self._extract_abstract_defensive(article, pmid)
            
            # Authors - use defensive extraction
            authors = self._extract_authors_defensive(article, pmid)
            
            # Journal - should always exist
            journal = self._safe_get(article, 'Journal', 'Title', default='Unknown Journal')
            if journal == 'Unknown Journal':
                self._log_warning(pmid, "Journal name missing")
            
            # Publication date - use defensive extraction
            pub_date = self._extract_date_defensive(article, pmid)
            
            # Article types - can be empty list
            article_types = []
            if 'PublicationTypeList' in article:
                try:
                    article_types = [str(pt) for pt in article['PublicationTypeList']]
                except Exception as e:
                    self._log_warning(pmid, f"Error parsing article types: {e}")
            
            # DOI - optional, handle carefully
            doi = None
            try:
                if 'ELocationID' in article:
                    eloc_list = article['ELocationID']
                    if eloc_list and isinstance(eloc_list, list):
                        for eloc in eloc_list:
                            if hasattr(eloc, 'attributes'):
                                if eloc.attributes.get('EIdType') == 'doi':
                                    doi = str(eloc)
                                    break
            except Exception as e:
                self._log_warning(pmid, f"Error parsing DOI: {e}")
            
            # Build guaranteed structure
            article_data = {
                'pmid': pmid,
                'title': str(title),
                'abstract': str(abstract),  # Guaranteed string
                'authors': list(authors),   # Guaranteed list
                'journal': str(journal),
                'pub_date': str(pub_date),
                'article_types': list(article_types),
                'doi': doi,  # Can be None (optional field)
                'citations': None,  # To be populated later
                'included': True,
                'user_notes': ""
            }
            
            return article_data
        
        except Exception as e:
            # Ultimate fallback - should never happen with defensive code above
            pmid = 'UNKNOWN'
            self._log_warning(pmid, f"Critical error parsing article: {str(e)}")
            
            # Return minimal valid structure
            return {
                'pmid': 'ERROR',
                'title': 'Error parsing article',
                'abstract': '',
                'authors': [],
                'journal': 'Unknown',
                'pub_date': 'Unknown',
                'article_types': [],
                'doi': None,
                'citations': None,
                'included': False,  # Mark as excluded
                'user_notes': f'Parse error: {str(e)}'
            }
    
    
    def _extract_abstract_defensive(self, article: Dict, pmid: str) -> str:
        """
        Defensively extract abstract from article record.
        
        Handles multiple cases:
        1. No abstract field (editorials, letters)
        2. Abstract exists but AbstractText missing
        3. AbstractText as single string
        4. AbstractText as list of strings (structured abstract)
        5. AbstractText with labels (Background:, Methods:, etc.)
        6. Empty or malformed abstract
        
        Args:
            article: Article record from PubMed
            pmid: PubMed ID for logging
        
        Returns:
            str: Abstract text, guaranteed non-None (empty string if missing)
        """
        # Check if Abstract field exists at all
        if 'Abstract' not in article:
            self._log_warning(pmid, "No abstract field available")
            return ""
        
        # Check if AbstractText exists within Abstract
        abstract_data = article['Abstract']
        if 'AbstractText' not in abstract_data:
            self._log_warning(pmid, "Abstract field exists but no AbstractText")
            return ""
        
        abstract_parts = abstract_data['AbstractText']
        
        # Handle None or empty
        if not abstract_parts:
            self._log_warning(pmid, "AbstractText is empty")
            return ""
        
        try:
            # Case 1: Single string
            if isinstance(abstract_parts, str):
                return abstract_parts.strip()
            
            # Case 2: List of strings or dict-like objects
            if isinstance(abstract_parts, list):
                text_parts = []
                for part in abstract_parts:
                    # Structured abstract with labels
                    if hasattr(part, 'attributes') and 'Label' in part.attributes:
                        label = part.attributes['Label']
                        text_parts.append(f"{label}: {str(part)}")
                    else:
                        text_parts.append(str(part))
                
                return " ".join(text_parts).strip()
            
            # Case 3: Unknown type - convert to string
            return str(abstract_parts).strip()
        
        except Exception as e:
            self._log_warning(pmid, f"Error parsing abstract: {str(e)}")
            return ""
    
    
    def _extract_authors_defensive(self, article: Dict, pmid: str) -> List[str]:
        """
        Defensively extract author list from article record.
        
        Handles:
        1. No AuthorList field
        2. Empty AuthorList
        3. Authors with LastName + ForeName
        4. Authors with only LastName or Initials
        5. CollectiveName (e.g., "WHO COVID-19 Study Group")
        6. Malformed author entries
        
        Args:
            article: Article record from PubMed
            pmid: PubMed ID for logging
        
        Returns:
            List[str]: Author names, guaranteed non-None (empty list if missing)
        """
        # Check if AuthorList exists
        if 'AuthorList' not in article:
            self._log_warning(pmid, "No author list available")
            return []
        
        author_list = article['AuthorList']
        
        # Handle empty AuthorList
        if not author_list:
            self._log_warning(pmid, "Author list is empty")
            return []
        
        authors = []
        
        try:
            for author in author_list:
                author_name = None
                
                # Case 1: Collective name (e.g., research groups)
                if 'CollectiveName' in author:
                    author_name = author['CollectiveName']
                
                # Case 2: Individual author with LastName
                elif 'LastName' in author:
                    last_name = author.get('LastName', '').strip()
                    fore_name = author.get('ForeName', '').strip()
                    initials = author.get('Initials', '').strip()
                    
                    # Prefer ForeName, fallback to Initials
                    if fore_name:
                        author_name = f"{fore_name} {last_name}"
                    elif initials:
                        author_name = f"{initials} {last_name}"
                    else:
                        author_name = last_name
                
                # Case 3: Only Initials (rare but happens)
                elif 'Initials' in author:
                    author_name = author['Initials']
                
                # Add to list if we got something valid
                if author_name and author_name.strip():
                    authors.append(author_name.strip())
                else:
                    self._log_warning(pmid, f"Malformed author entry: {author}")
        
        except Exception as e:
            self._log_warning(pmid, f"Error parsing authors: {str(e)}")
        
        # Warn if we ended up with no authors
        if not authors:
            self._log_warning(pmid, "No valid authors could be extracted")
        
        return authors
    
    
    def _extract_date_defensive(self, article: Dict, pmid: str) -> str:
        """
        Defensively extract publication date from article record.
        
        PubMed dates can be:
        1. Complete: YYYY-MM-DD
        2. Year + Month: YYYY-MM
        3. Year only: YYYY
        4. Season: "Spring 2020", "2020 Fall"
        5. Medline date: "2020 Jan-Feb"
        6. Completely missing
        
        Priority order:
        1. ArticleDate (electronic publication)
        2. Journal PubDate (print publication)
        3. MedlineDate (text date)
        4. "Unknown" if all fail
        
        Args:
            article: Article record from PubMed
            pmid: PubMed ID for logging
        
        Returns:
            str: Date in YYYY-MM-DD, YYYY-MM, or YYYY format, or "Unknown"
        """
        
        # Try 1: Electronic publication date (most accurate)
        article_date = self._safe_get(article, 'ArticleDate')
        if article_date and len(article_date) > 0:
            date_dict = article_date[0]
            year = date_dict.get('Year', '')
            month = date_dict.get('Month', '').zfill(2) if date_dict.get('Month') else None
            day = date_dict.get('Day', '').zfill(2) if date_dict.get('Day') else None
            
            if year:
                if month and day:
                    return f"{year}-{month}-{day}"
                elif month:
                    return f"{year}-{month}"
                else:
                    return year
        
        # Try 2: Journal publication date
        pub_date = self._safe_get(article, 'Journal', 'JournalIssue', 'PubDate')
        if pub_date:
            # Handle MedlineDate (text format like "2020 Jan-Feb")
            if 'MedlineDate' in pub_date:
                medline_date = pub_date['MedlineDate']
                # Extract year from medline date using regex
                year_match = re.search(r'\d{4}', medline_date)
                if year_match:
                    return year_match.group(0)
            
            # Handle structured date
            year = pub_date.get('Year', '')
            month = pub_date.get('Month', '')
            day = pub_date.get('Day', '')
            
            if year:
                # Convert month name to number if needed
                if month and not month.isdigit():
                    month = self._month_to_number(month)
                
                month = str(month).zfill(2) if month and str(month).isdigit() else None
                day = str(day).zfill(2) if day and str(day).isdigit() else None
                
                if month and day:
                    return f"{year}-{month}-{day}"
                elif month:
                    return f"{year}-{month}"
                else:
                    return year
        
        # All methods failed
        self._log_warning(pmid, "Could not extract publication date")
        return "Unknown"
    
    
    def _month_to_number(self, month_str: str) -> str:
        """
        Convert month name to number.
        
        Args:
            month_str (str): Month name (e.g., "Jan", "January")
        
        Returns:
            str: Month number (e.g., "01")
        """
        months = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        return months.get(month_str.lower()[:3], '01')
    
    
    def _build_date_filter(self, date_from: str = None, date_to: str = None) -> str:
        """
        Build PubMed date range filter string.
        
        Args:
            date_from (str, optional): Start date YYYY/MM/DD
            date_to (str, optional): End date YYYY/MM/DD
        
        Returns:
            str: PubMed date filter syntax
        """
        if date_from and date_to:
            return f'"{date_from}"[Date - Publication] : "{date_to}"[Date - Publication]'
        elif date_from:
            return f'"{date_from}"[Date - Publication] : "3000"[Date - Publication]'
        elif date_to:
            return f'"1800"[Date - Publication] : "{date_to}"[Date - Publication]'
        else:
            return ""
    
    
    def _safe_get(self, dictionary: Dict, *keys, default=None):
        """
        Safely navigate nested dictionary structure.
        
        Prevents KeyError when accessing deeply nested dict paths.
        
        Args:
            dictionary: The dict to navigate
            *keys: Sequence of keys to traverse
            default: Value to return if path doesn't exist
        
        Returns:
            The value if all keys exist, otherwise default
        
        Example:
            _safe_get(record, 'MedlineCitation', 'Article', 'Title', default='No title')
        """
        current = dictionary
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
    
    
    def _log_warning(self, pmid: str, message: str):
        """
        Log a warning about missing or problematic data.
        
        Warnings are stored and can be retrieved later for analysis.
        
        Args:
            pmid: The PubMed ID of the problematic article
            message: Description of the issue
        """
        warning_msg = f"[PMID {pmid}] {message}"
        print(f"  ⚠ {warning_msg}")
        
        # Store warning for later analysis
        self.warnings.append({
            'pmid': pmid,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
    
    
    def get_warnings(self) -> List[Dict]:
        """
        Get all warnings logged during parsing.
        
        Useful for:
        - Debugging data quality issues
        - Identifying problematic PMIDs
        - Analyzing patterns in missing data
        
        Returns:
            List[Dict]: List of warnings with pmid, message, and timestamp
        """
        return self.warnings
    
    
    def clear_warnings(self):
        """Clear all accumulated warnings."""
        self.warnings = []
    
    
    def print_warning_summary(self):
        """
        Print a summary of all warnings grouped by type.
        
        Useful for understanding data quality patterns.
        """
        if not self.warnings:
            print("\n✓ No warnings - all articles parsed successfully!")
            return
        
        print(f"\n{'='*60}")
        print(f"WARNING SUMMARY: {len(self.warnings)} total warnings")
        print(f"{'='*60}")
        
        # Group warnings by message type
        warning_types = {}
        for warning in self.warnings:
            msg = warning['message']
            if msg not in warning_types:
                warning_types[msg] = []
            warning_types[msg].append(warning['pmid'])
        
        # Print grouped warnings
        for msg, pmids in sorted(warning_types.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"\n{len(pmids)}x - {msg}")
            print(f"   PMIDs: {', '.join(pmids[:5])}{'...' if len(pmids) > 5 else ''}")


# Example usage when running this file directly
if __name__ == "__main__":
    print("="*60)
    print("PubMed Agent - DEFENSIVE MODE - Standalone Test")
    print("="*60)
    
    # Create agent instance
    agent = PubMedAgent()
    
    # Test search and fetch with a cardiosurgery topic
    articles = agent.search_and_fetch(
        query="aortic dissection surgery",
        max_results=10,  # Increased to test more edge cases
        date_from="2020/01/01"
    )
    
    # Display results
    print(f"\n{'='*60}")
    print(f"RESULTS: {len(articles)} articles found")
    print(f"{'='*60}\n")
    
    for i, article in enumerate(articles, 1):
        print(f"{i}. [{article['pmid']}] {article['title']}")
        print(f"   Journal: {article['journal']}")
        print(f"   Date: {article['pub_date']}")
        print(f"   Authors: {', '.join(article['authors'][:3])}{'...' if len(article['authors']) > 3 else ''}")
        print(f"   Type: {', '.join(article['article_types'])}")
        if article['abstract']:
            print(f"   Abstract: {article['abstract'][:150]}...")
        else:
            print(f"   Abstract: [No abstract available]")
        print()
    
    # Print warning summary
    agent.print_warning_summary()