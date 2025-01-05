import os
import requests
from typing import Optional, Dict, Any, Union, List
from enum import Enum
from dotenv import load_dotenv

class QuerySelector(Enum):
    """Available query selector types for concordance search."""
    IQUERY = "iqueryrow"
    CQL = "cqlrow"
    LEMMA = "lemmarow"
    CHAR = "charrow"
    WORD = "wordrow"
    PHRASE = "phraserow"

class ViewMode(Enum):
    """Available view modes for concordance results."""
    SENTENCE = "sen"
    KWIC = "kwic"

class SketchEngineClient:
    """Client for interacting with the Sketch Engine API."""
    
    BASE_URL = "https://api.sketchengine.eu"
    
    def __init__(self, api_key: Optional[str] = None, username: Optional[str] = None):
        """Initialize the Sketch Engine client.
        
        Args:
            api_key: Optional API key. If not provided, will look for SKETCH_ENGINE_API_KEY in env.
            username: Optional username. If not provided, will look for SKETCH_ENGINE_USERNAME in env.
        """
        load_dotenv()
        
        self.api_key = api_key or os.getenv("SKETCH_ENGINE_API_KEY")
        self.username = username or os.getenv("SKETCH_ENGINE_USERNAME")
        
        if not self.api_key:
            raise ValueError("API key must be provided either directly or via SKETCH_ENGINE_API_KEY env var")
        if not self.username:
            raise ValueError("Username must be provided either directly or via SKETCH_ENGINE_USERNAME env var")
            
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        })
    
    def health_check(self) -> bool:
        """Check if the API is accessible and credentials are valid.
        
        Returns:
            bool: True if API is accessible and credentials are valid, False otherwise.
        """
        try:
            # Using the concordance endpoint with minimal parameters as a health check
            response = self.session.get(
                f"{self.BASE_URL}/search/concordance",
                params={"corpname": "preloaded/magyarok_hp2", "pagesize": 1}
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def concordance_search(
        self,
        corpname: str,
        q: Optional[str] = None,
        query_type: Optional[QuerySelector] = None,
        query: Optional[str] = None,
        usesubcorp: Optional[str] = None,
        lpos: Optional[str] = None,
        default_attr: Optional[str] = None,
        attrs: Optional[Union[str, List[str]]] = None,
        refs: Optional[str] = None,
        attr_allpos: Optional[str] = None,
        viewmode: Optional[ViewMode] = None,
        cup_hl: Optional[str] = None,
        structs: Optional[Union[str, List[str]]] = None,
        fromp: Optional[int] = 1,
        pagesize: Optional[int] = 20,
        kwicleftctx: Optional[str] = "100#",
        kwicrightctx: Optional[str] = "100#",
        asyn: Optional[int] = None,
        format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Perform a concordance search in the specified corpus.
        
        Args:
            corpname: Corpus name (e.g. 'preloaded/magyarok_hp2')
            q: Primary query string (CQL, iquery, etc.)
            query_type: Type of query being used (e.g. QuerySelector.PHRASE)
            query: The actual query string matching the query_type
            usesubcorp: Name of subcorpus to use
            lpos: Part-of-speech of the lemma
            default_attr: Default attribute for tokens in query
            attrs: Attributes to return with each token (comma-separated or list)
            refs: Text types for statistics
            attr_allpos: Whether to return additional attributes in KWIC or all
            viewmode: View mode for results (sentence or KWIC)
            cup_hl: Highlighting for error-annotated corpora
            structs: Structural tags to include (comma-separated or list)
            fromp: Page number (1-based)
            pagesize: Number of results per page
            kwicleftctx: Size of left context in KWIC view
            kwicrightctx: Size of right context in KWIC view
            asyn: Whether to use asynchronous processing
            format: Output format (default JSON)
            
        Returns:
            Dict containing the concordance search results
            
        Raises:
            requests.RequestException: If the API request fails
            ValueError: If required parameters are missing or invalid
        """
        if not corpname:
            raise ValueError("corpname is required")
            
        # Build query parameters
        params: Dict[str, Any] = {
            "corpname": corpname,
            "fromp": fromp,
            "pagesize": pagesize
        }
        
        # Add optional parameters if provided
        if q:
            params["q"] = q
            # When using q parameter, we need to specify queryselector
            params["concordance_query[queryselector]"] = "cqlrow"  # CQL is the default for direct queries
        elif query_type and query:
            params["concordance_query[queryselector]"] = query_type.value
            params[f"concordance_query[{query_type.value.replace('row', '')}]"] = query
        if usesubcorp:
            params["usesubcorp"] = usesubcorp
        if lpos:
            params["lpos"] = lpos
        if default_attr:
            params["default_attr"] = default_attr
        if attrs:
            params["attrs"] = ",".join(attrs) if isinstance(attrs, list) else attrs
        if refs:
            params["refs"] = refs
        if attr_allpos:
            params["attr_allpos"] = attr_allpos
        if viewmode:
            params["viewmode"] = viewmode.value
        if cup_hl:
            params["cup_hl"] = cup_hl
        if structs:
            params["structs"] = ",".join(structs) if isinstance(structs, list) else structs
        if kwicleftctx:
            params["kwicleftctx"] = kwicleftctx
        if kwicrightctx:
            params["kwicrightctx"] = kwicrightctx
        if asyn is not None:
            params["asyn"] = asyn
        if format:
            params["format"] = format
            
        response = self.session.get(f"{self.BASE_URL}/search/concordance", params=params)
        response.raise_for_status()
        return response.json()

if __name__ == "__main__":
    # Example usage
    client = SketchEngineClient()
    
    # First check if API is accessible
    is_healthy = client.health_check()
    print(f"API Health Check: {'✓' if is_healthy else '✗'}")
    
    if is_healthy:
        try:
            # Example concordance search using exact parameters from curl command
            results = client.concordance_search(
                corpname="preloaded/magyarok_hp2",
                q='q[word="kérem"]',
                query_type=QuerySelector.PHRASE,
                attrs="word",
                refs="=bncdoc.alltyp",
                attr_allpos="all",
                structs=["s", "g"],
                fromp=1,
                pagesize=20,
                kwicleftctx="100#",
                kwicrightctx="100#"
            )
            
            if "error" in results:
                print("\nError in search:")
                print(f"Error: {results['error']}")
                print("Request parameters:")
                print(results.get("request", {}))
            else:
                print("\nConcordance Search Results:")
                if "Lines" in results:
                    print(f"Found {len(results['Lines'])} results:")
                    for line in results["Lines"]:
                        print(line)
                else:
                    print("No results found in the expected format")
                    print(results)
        except Exception as e:
            print(f"Search failed: {e}") 