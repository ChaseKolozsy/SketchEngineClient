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

class DiffBy(Enum):
    """Available comparison modes for word sketch differences."""
    LEMMA = "lemma"
    WORD_FORM = "word form"
    SUBCORPUS = "subcorpus"

class WSketchSortMode(Enum):
    """Available sorting modes for word sketch collocates."""
    SCORE = "s"
    FREQUENCY = "f"

class WordlistFreqType(Enum):
    """Available frequency types for wordlist."""
    RAW_FREQ = "freq"
    DOC_FREQ = "docf"
    AVG_REDUCED_FREQ = "arf"

class WordlistSortMode(Enum):
    """Available sorting modes for wordlist."""
    FREQUENCY = "freq"
    DOC_FREQUENCY = "docf"

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
        
        For basic searches, only corpname and q parameters are required.
        The concordance allows complex criteria for searching the corpus.
        The queries can combine any data, metadata and annotations found in the corpus.
        
        Args:
            corpname: Corpus name (e.g. 'preloaded/magyarok_hp2')
            q: Primary query string (CQL, iquery, etc.). For basic searches, this is all you need with corpname.
            query_type: Type of query being used (e.g. QuerySelector.PHRASE) when not using direct q parameter
            query: The actual query string matching the query_type when not using direct q parameter
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
            "corpname": corpname
        }
        
        # Handle pagination parameters
        if fromp is not None:
            params["fromp"] = fromp
        if pagesize is not None:
            params["pagesize"] = pagesize
        
        # Handle query parameters - prefer direct q parameter if provided
        if q:
            params["q"] = q
        elif query_type and query:
            params["concordance_query[queryselector]"] = query_type.value
            params[f"concordance_query[{query_type.value.replace('row', '')}]"] = query
        
        # Add optional parameters if provided
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

    def wsdiff_search(
        self,
        corpname: str,
        lemma: str,
        diff_by: Optional[DiffBy] = None,
        lpos: Optional[str] = None,
        lemma2: Optional[str] = None,
        minfreq: Optional[Union[str, int]] = None,
        maxcommon: Optional[int] = None,
        separate_blocks: Optional[int] = None,
        maxexclusive: Optional[int] = None,
        wordform1: Optional[str] = None,
        wordform2: Optional[str] = None,
        subcorp1: Optional[str] = None,
        subcorp2: Optional[str] = None,
        format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Perform a word sketch difference search comparing two lemmas, word forms, or subcorpora.
        
        Args:
            corpname: Corpus name (e.g. 'preloaded/magyarok_hp2')
            lemma: The base form of the first lemma to compare
            diff_by: The mode of comparison (lemma, word form, or subcorpus)
            lpos: The part of speech of the lemma
            lemma2: The second lemma to compare (required if diff_by=lemma)
            minfreq: Minimum frequency of a collocate (integer or 'auto')
            maxcommon: Maximum number of collocates in a single table (default 12)
            separate_blocks: 1 => produce separate blocks by grammatical relation; 0 => single list
            maxexclusive: Maximum number of collocates for an individual lemma (requires separate_blocks=1)
            wordform1: The first word form to compare (required if diff_by=word form)
            wordform2: The second word form to compare (required if diff_by=word form)
            subcorp1: The first subcorpus name (required if diff_by=subcorpus)
            subcorp2: The second subcorpus name (required if diff_by=subcorpus)
            format: Output format (default JSON)
            
        Returns:
            Dict containing the word sketch difference results
            
        Raises:
            requests.RequestException: If the API request fails
            ValueError: If required parameters are missing or invalid
        """
        if not corpname or not lemma:
            raise ValueError("corpname and lemma are required")
            
        # Build query parameters
        params: Dict[str, Any] = {
            "corpname": corpname,
            "lemma": lemma
        }
        
        # Handle diff_by specific requirements
        if diff_by:
            params["diff_by"] = diff_by.value
            
            if diff_by == DiffBy.LEMMA and not lemma2:
                raise ValueError("lemma2 is required when diff_by=lemma")
            elif diff_by == DiffBy.WORD_FORM and (not wordform1 or not wordform2):
                raise ValueError("wordform1 and wordform2 are required when diff_by=word form")
            elif diff_by == DiffBy.SUBCORPUS and (not subcorp1 or not subcorp2):
                raise ValueError("subcorp1 and subcorp2 are required when diff_by=subcorpus")
        
        # Add optional parameters if provided
        if lpos:
            params["lpos"] = lpos
        if lemma2:
            params["lemma2"] = lemma2
        if minfreq is not None:
            params["minfreq"] = str(minfreq)
        if maxcommon is not None:
            params["maxcommon"] = maxcommon
        if separate_blocks is not None:
            params["separate_blocks"] = separate_blocks
        if maxexclusive is not None:
            params["maxexclusive"] = maxexclusive
        if wordform1:
            params["wordform1"] = wordform1
        if wordform2:
            params["wordform2"] = wordform2
        if subcorp1:
            params["subcorp1"] = subcorp1
        if subcorp2:
            params["subcorp2"] = subcorp2
        if format:
            params["format"] = format
            
        response = self.session.get(f"{self.BASE_URL}/search/wsdiff", params=params)
        response.raise_for_status()
        return response.json()

    def thes_search(
        self,
        corpname: str,
        lemma: str,
        lpos: Optional[str] = None,
        usesubcorp: Optional[str] = None,
        minthesscore: Optional[int] = None,
        maxthesitems: Optional[int] = None,
        clustertitems: Optional[int] = None,
        minsim: Optional[int] = None,
        format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a list of words similar in meaning or belonging to the same semantic group.
        
        Args:
            corpname: Corpus name (e.g. 'preloaded/magyarok_hp2')
            lemma: The base form of the word to query synonyms for
            lpos: Part of speech for the lemma
            usesubcorp: Name of the subcorpus (defaults to entire corpus)
            minthesscore: Minimum score for the thesaurus list
            maxthesitems: Maximum number of items to display
            clustertitems: Whether to cluster items by similarity in meaning (0 or 1)
            minsim: Minimum similarity threshold used when clustertitems=1
            format: Output format (defaults to JSON)
            
        Returns:
            Dict containing the thesaurus results with similar words and their scores
            
        Raises:
            requests.RequestException: If the API request fails
            ValueError: If required parameters are missing or invalid
        """
        if not corpname or not lemma:
            raise ValueError("corpname and lemma are required")
            
        # Build query parameters
        params: Dict[str, Any] = {
            "corpname": corpname,
            "lemma": lemma
        }
        
        # Add optional parameters if provided
        if lpos:
            params["lpos"] = lpos
        if usesubcorp:
            params["usesubcorp"] = usesubcorp
        if minthesscore is not None:
            params["minthesscore"] = minthesscore
        if maxthesitems is not None:
            params["maxthesitems"] = maxthesitems
        if clustertitems is not None:
            if clustertitems not in (0, 1):
                raise ValueError("clustertitems must be 0 or 1")
            params["clustertitems"] = clustertitems
        if minsim is not None:
            params["minsim"] = minsim
        if format:
            params["format"] = format
            
        response = self.session.get(f"{self.BASE_URL}/search/thes", params=params)
        response.raise_for_status()
        return response.json()

    def wsketch_search(
        self,
        corpname: str,
        lemma: str,
        lpos: Optional[str] = None,
        usesubcorp: Optional[str] = None,
        minfreq: Optional[Union[str, int]] = None,
        minscore: Optional[Union[str, int]] = None,
        minsim: Optional[int] = None,
        maxitems: Optional[int] = None,
        clustercolls: Optional[int] = None,
        expand_seppage: Optional[int] = None,
        sort_ws_columns: Optional[WSketchSortMode] = None,
        structured: Optional[str] = None,
        bim_corpname: Optional[str] = None,
        bim_lemma: Optional[str] = None,
        bim_lpos: Optional[str] = None,
        format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate word combinations (collocations) sorted by typicality or frequency.
        
        Args:
            corpname: Corpus name (e.g. 'preloaded/magyarok_hp2')
            lemma: Base form of the word (lemma) to get a word sketch for
            lpos: Part of speech for the lemma
            usesubcorp: Name of a subcorpus to restrict the word sketch
            minfreq: Minimum frequency below which collocates are hidden (integer or 'auto')
            minscore: The minimum logDice score of the collocates
            minsim: The minimum similarity threshold when clusterColls=1
            maxitems: Maximum number of items in each grammatical relation block
            clustercolls: Groups collocates by similarity in meaning if set to 1
            expand_seppage: 1 => show grammatical relations grouped together on separate pages
            sort_ws_columns: Sort collocates by score (s) or absolute frequency (f)
            structured: 1 => grouped into grammatical relations; 0 => single unstructured list
            bim_corpname: Second corpus for bilingual word sketches
            bim_lemma: The lemma in the second corpus, for bilingual word sketches
            bim_lpos: The part of speech of the lemma in the second corpus
            format: Output format (defaults to JSON)
            
        Returns:
            Dict containing the word sketch results with collocations
            
        Raises:
            requests.RequestException: If the API request fails
            ValueError: If required parameters are missing or invalid
        """
        if not corpname or not lemma:
            raise ValueError("corpname and lemma are required")
            
        # Build query parameters
        params: Dict[str, Any] = {
            "corpname": corpname,
            "lemma": lemma
        }
        
        # Add optional parameters if provided
        if lpos:
            params["lpos"] = lpos
        if usesubcorp:
            params["usesubcorp"] = usesubcorp
        if minfreq is not None:
            params["minfreq"] = str(minfreq)
        if minscore is not None:
            params["minscore"] = str(minscore)
        if minsim is not None:
            params["minsim"] = minsim
        if maxitems is not None:
            params["maxitems"] = maxitems
        if clustercolls is not None:
            if clustercolls not in (0, 1):
                raise ValueError("clustercolls must be 0 or 1")
            params["clustercolls"] = clustercolls
        if expand_seppage is not None:
            if expand_seppage not in (0, 1):
                raise ValueError("expand_seppage must be 0 or 1")
            params["expand_seppage"] = expand_seppage
        if sort_ws_columns:
            params["sort_ws_columns"] = sort_ws_columns.value
        if structured is not None:
            if structured not in ("0", "1"):
                raise ValueError("structured must be '0' or '1'")
            params["structured"] = structured
        
        # Handle bilingual word sketch parameters
        if any([bim_corpname, bim_lemma, bim_lpos]):
            if not all([bim_corpname, bim_lemma]):
                raise ValueError("Both bim_corpname and bim_lemma are required for bilingual word sketches")
            params["bim_corpname"] = bim_corpname
            params["bim_lemma"] = bim_lemma
            if bim_lpos:
                params["bim_lpos"] = bim_lpos
                
        if format:
            params["format"] = format
            
        response = self.session.get(f"{self.BASE_URL}/search/wsketch", params=params)
        response.raise_for_status()
        return response.json()

    def wordlist_search(
        self,
        corpname: str,
        wlattr: str,
        usesubcorp: Optional[str] = None,
        wlnums: Optional[WordlistFreqType] = None,
        wlmaxfreq: Optional[int] = None,
        wlminfreq: Optional[int] = None,
        wlpat: Optional[str] = None,
        wlsort: Optional[WordlistSortMode] = None,
        wlblacklist: Optional[Union[str, List[str]]] = None,
        include_nonwords: Optional[int] = None,
        relfreq: Optional[int] = None,
        reldocf: Optional[int] = None,
        wlfile: Optional[str] = None,
        wlicase: Optional[int] = None,
        wlmaxitems: Optional[int] = None,
        wlpage: Optional[int] = None,
        format: Optional[str] = None,
        random: Optional[int] = None,
        wltype: Optional[str] = None,
        ngrams_n: Optional[int] = None,
        ngrams_max_n: Optional[int] = None,
        nest_ngrams: Optional[int] = None,
        simple_n: Optional[int] = None,
        usengrams: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate frequency lists of all tokens, lemmas, word forms, etc.
        
        This method can be used for generating frequency lists of all tokens, lemmas, word forms etc. 
        or for retrieving frequencies of concrete items. Regex can be used for detailed criteria.
        
        Args:
            corpname: Corpus name (e.g. 'preloaded/magyarok_hp2')
            wlattr: Attribute to count (e.g. word, lc, lemma, lemma_lc, tag, pos)
            usesubcorp: Subcorpus name (defaults to entire corpus)
            wlnums: Type of frequency to show (raw freq, doc freq, or avg reduced freq)
            wlmaxfreq: Maximum frequency limit (items above this are not shown)
            wlminfreq: Minimum frequency limit (items below this are excluded)
            wlpat: Regex pattern to filter items (e.g. .* to match all)
            wlsort: Sorting of the results (by frequency or document frequency)
            wlblacklist: List of items to exclude (string with newline separators or list)
            include_nonwords: Whether to include tokens not starting with letters (0 or 1)
            relfreq: Include relative frequency of each item (0 or 1)
            reldocf: Calculate document frequency for each item (0 or 1)
            wlfile: A whitelist file with items to include
            wlicase: Case-sensitive search (0 or 1)
            wlmaxitems: Maximum number of items to return
            wlpage: Page number for paginated results
            format: Output format (defaults to JSON)
            random: Return random sample of size n
            wltype: Type of wordlist (basic, advanced, etc.)
            ngrams_n: Size of n-grams
            ngrams_max_n: Maximum size of n-grams
            nest_ngrams: Whether to nest n-grams (0 or 1)
            simple_n: Simple n-gram size
            usengrams: Whether to use n-grams (0 or 1)
            
        Returns:
            Dict containing the wordlist results
            
        Raises:
            requests.RequestException: If the API request fails
            ValueError: If required parameters are missing or invalid
        """
        if not corpname or not wlattr:
            raise ValueError("corpname and wlattr are required")
            
        # Build query parameters
        params: Dict[str, Any] = {
            "corpname": corpname,
            "wlattr": wlattr
        }
        
        # Add optional parameters if provided
        if usesubcorp:
            params["usesubcorp"] = usesubcorp
        if wlnums:
            params["wlnums"] = wlnums.value
        if wlmaxfreq is not None:
            params["wlmaxfreq"] = wlmaxfreq
        if wlminfreq is not None:
            params["wlminfreq"] = wlminfreq
        if wlpat:
            params["wlpat"] = wlpat
        if wlsort:
            params["wlsort"] = wlsort.value
        if wlblacklist:
            # Convert list to newline-separated string if needed
            if isinstance(wlblacklist, list):
                params["wlblacklist"] = "%0A".join(wlblacklist)
            else:
                params["wlblacklist"] = wlblacklist
        if include_nonwords is not None:
            if include_nonwords not in (0, 1):
                raise ValueError("include_nonwords must be 0 or 1")
            params["include_nonwords"] = include_nonwords
        if relfreq is not None:
            if relfreq not in (0, 1):
                raise ValueError("relfreq must be 0 or 1")
            params["relfreq"] = relfreq
        if reldocf is not None:
            if reldocf not in (0, 1):
                raise ValueError("reldocf must be 0 or 1")
            params["reldocf"] = reldocf
        if wlfile:
            params["wlfile"] = wlfile
        if wlicase is not None:
            if wlicase not in (0, 1):
                raise ValueError("wlicase must be 0 or 1")
            params["wlicase"] = wlicase
        if wlmaxitems is not None:
            params["wlmaxitems"] = wlmaxitems
        if wlpage is not None:
            params["wlpage"] = wlpage
        if format:
            params["format"] = format
        if random is not None:
            params["random"] = random
        if wltype:
            params["wltype"] = wltype
            
        # N-gram related parameters
        if ngrams_n is not None:
            params["ngrams_n"] = ngrams_n
        if ngrams_max_n is not None:
            params["ngrams_max_n"] = ngrams_max_n
        if nest_ngrams is not None:
            if nest_ngrams not in (0, 1):
                raise ValueError("nest_ngrams must be 0 or 1")
            params["nest_ngrams"] = nest_ngrams
        if simple_n is not None:
            params["simple_n"] = simple_n
        if usengrams is not None:
            if usengrams not in (0, 1):
                raise ValueError("usengrams must be 0 or 1")
            params["usengrams"] = usengrams
            
        response = self.session.get(f"{self.BASE_URL}/search/wordlist", params=params)
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