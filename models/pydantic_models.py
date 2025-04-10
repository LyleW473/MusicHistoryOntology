from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict


# Base model for common fields
class BaseEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")  # Disallow extra fields
    hasName: str = Field(..., description="Primary name or label of the entity")
    hasDescription: Optional[str] = Field(
        None, description="Description of the entity (if available)"
        )  # Optional description
    identifier: str = Field(
        ...,
        description="Unique identifier for the entity (e.g., EntityType_MBID or EntityType_SanitizedName)",
    )
    entity_type: str = Field(
        ..., description="The class name of the entity (e.g., Musician, MusicGenre)"
    )


# --- Specific Entity Models ---


class Place(BaseEntity):
    entity_type: str = "Place"
    # From Place in mappings
    # object_properties: hasAddress (Address), hasContinent (Continent), isBirthPlaceOf (Person), isFormationPlaceOf (MusicEnsenble), isPlaceOf (Thing)
    # data_properties: name, description
    # address: Optional[str] = Field(
    #     None, description="Textual representation of the address"
    # )  # Keep simple for now
    # coordinates: Optional[Dict[str, float]] = Field(
    #     None, description="Latitude/Longitude dictionary"
    # )  # MB specific
    # place_type: Optional[str] = Field(
    #     None, description="Type of place (e.g., Venue, City, Country) from MB"
    # )  # MB specific

class Country(BaseEntity):
    entity_type: str = "Country"
    # From Country mappings
    # data_properties: name, description
    iso_code: Optional[str] = Field(
        None, description="ISO 3166-1 alpha-2 code"
    )  # Specific to Country


class TimeInterval(BaseEntity):
    entity_type: str = "TimeInterval"
    # From TimeInterval mappings
    # object_properties: isTimeIntervalOf (Thing)
    # data_properties: startTime, endTime, description, name
    hasStartTime: Optional[str] = Field(
        None, description="Start date of the interval (YYYY-MM-DD)"
    )
    hasEndTime: Optional[str] = Field(
        None, description="End date of the interval (YYYY-MM-DD)"
    )
    # Optional: hasIntervalDate if it's a single point in time?


class MusicGenre(BaseEntity):
    entity_type: str = "MusicGenre"
    # From MusicGenre mappings
    # object_properties: isGenreOf (MusicArtist) - This link is stored on the Artist side
    # data_properties: name, description


class Instrument(BaseEntity):
    entity_type: str = "Instrument"
    # From Instrument mappings
    # object_properties: wasInventedBy (Agent -> Musician identifier), wasInventedAtTime (TimeInterval identifier)
    # data_properties: name, description
    wasInventedBy: Optional[List[str]] = Field(
        None, description="List of identifiers for the inventor(s) (Musician)"
    )  # Mapping says Agent, assume Musician
    inventionDate: Optional[str] = Field(
        None, description="Invention date (YYYY-MM-DD)"
    )  # Map wasInventedAtTime loosely here
    instrument_type: Optional[str] = Field(
        None, description="Type of instrument (e.g., string, wind) from MB"
    )  # MB specific


class RecordLabel(BaseEntity):
    entity_type: str = "RecordLabel"
    # From RecordLabel mappings
    # object_properties: hasSigned (Musician) - Link stored on Musician side (wasSignedTo)
    # data_properties: name, description
    label_type: Optional[str] = Field(
        None, description="Type of label (e.g., Distributor) from MB"
    )  # MB specific


class MusicEnsembleMembership(BaseEntity):
    entity_type: str = "MusicEnsembleMembership"
    # From MusicEnsembleMembership mappings
    # object_properties: involvesMemberOfMusicEnsemble (MusicArtist -> Musician/Ensemble ID), involvesMusicEnsemble (MusicEnsenble -> Ensemble ID), hasTimeInterval
    # data_properties: name, description (use name for role?)
    involvesMemberOfMusicEnsemble: Optional[str] = Field(
        None, description="Identifier of the member (Musician/Ensemble)"
    )
    involvesMusicEnsemble: Optional[str] = Field(
        None, description="Identifier of the ensemble"
    )
    hasTimeInterval: Optional[str] = Field(
        None,
        description="Identifier of the TimeInterval entity for membership duration",
    )
    # MB specific fields we captured previously
    # startDate: Optional[str] = Field(None, description="Start date of membership") # Covered by TimeInterval
    # endDate: Optional[str] = Field(None, description="End date of membership") # Covered by TimeInterval


# Use BaseEntity as parent for Artist types
class BaseArtist(BaseEntity):
    # Common properties for Musicians and Ensembles from MusicArtist mapping
    # object_properties: hasGenre (MusicGenre identifier list), nominatedForAward, receivedAward (Award identifiers), isInfluencedBy (MusicArtist identifier)
    # data_properties: name, description
    hasGenre: Optional[List[str]] = Field(
        None, description="List of identifiers for associated music genres"
    )
    # MB specific fields
    sort_name: Optional[str] = Field(None, description="Sort name from MB")
    disambiguation: Optional[str] = Field(
        None, description="Disambiguation comment from MB"
    )


class Musician(BaseArtist):
    entity_type: str = "Musician"
    # From Musician mappings (inherits from Person)
    # object_properties: hasBirthPlace (Place identifier), hasResidence (Place identifier), livesIn (Place identifier), wasSignedTo (RecordLabel identifier list)
    # data_properties: birthDate, deathDate, firstName, lastName, gender (added)
    firstName: Optional[str] = Field(None, description="First name")
    lastName: Optional[str] = Field(None, description="Last name")
    hasBirthDate: Optional[str] = Field(None, description="Birth date (YYYY-MM-DD)")
    hasDeathDate: Optional[str] = Field(
        None, description="Death date (YYYY-MM-DD), if applicable"
    )
    hasBirthPlace: Optional[str] = Field(
        None, description="Identifier of the place of birth"
    )
    livesIn: Optional[str] = Field(
        None, description="Identifier of the place of residence"
    )  # Mapping links to Place
    wasSignedTo: Optional[List[str]] = Field(
        None, description="List of RecordLabel identifiers"
    )  # Need to capture this
    gender: Optional[str] = Field(
        None, description="Gender ('male', 'female', etc.)"
    )  # from MB


class MusicEnsemble(BaseArtist):
    entity_type: str = "MusicEnsemble"  # Corrected spelling from mapping JSON key
    # From MusicEnsenble mappings
    # object_properties: wasFormedIn (Place identifier), hasMember (through MusicEnsembleMembership)
    # data_properties: formationDate, dissolutionDate (implicit via hasTimeInterval?)
    formationDate: Optional[str] = Field(
        None, description="Formation date (YYYY-MM-DD)"
    )
    dissolutionDate: Optional[str] = Field(
        None, description="Dissolution date (YYYY-MM-DD), if applicable"
    )
    wasFormedIn: Optional[str] = Field(
        None, description="Identifier of the place where the ensemble was formed"
    )
    # Link to memberships - the Membership JSON links back here
    memberships: Optional[List[str]] = Field(
        None,
        description="List of identifiers for MusicEnsembleMembership entities involving this ensemble",
    )


# Release types inherit from a common base?
class BaseRelease(BaseEntity):
    # Common properties from Release mapping
    # object_properties: wasReleasedIn (Country identifier list?), hasPublisher (Publisher identifier list)
    # data_properties: title, releaseDate (use first release date)
    hasTitle: Optional[str] = Field(
        None, description="The title of the release"
    )  # Overrides BaseEntity.name for clarity
    # Mappings don't explicitly list hasArtist/hasMusician on Release, but it's essential context. Add it.
    hasArtist: Optional[str] = Field(
        None, description="Identifier of the primary artist (Musician or MusicEnsemble)"
    )
    releaseDate: Optional[str] = Field(
        None, description="First release date (YYYY-MM-DD)"
    )
    hasGenre: Optional[List[str]] = Field(
        None,
        description="List of identifiers for associated music genres (from MB tags)",
    )  # Added, based on common practice


class Album(BaseRelease):
    entity_type: str = "Album"


class Single(BaseRelease):
    entity_type: str = "Single"


class Recording(BaseEntity):
    entity_type: str = "Recording"
    # From Recording mappings
    # object_properties: isPartOfRelease (Release identifier), isProducedByRecordingProcess (RecordingProcess ID)
    # data_properties: title, name (use title?), description
    hasTitle: Optional[str] = Field(None, description="The title of the recording")
    isPartOfRelease: Optional[str] = Field(
        None, description="Identifier of the Release this recording is part of"
    )
    # We don't process RecordingProcess yet
    # Optional: Link to Artist(s)? Link to Work?
    hasArtist: Optional[List[str]] = Field(
        None, description="Identifier(s) of performer(s)"
    )  # From MB artist credit
    # realizesWork: Optional[str] = Field(None, description="Identifier of the Work realized by this recording")
    duration: Optional[int] = Field(
        None, description="Duration in milliseconds (from MB)"
    )  # MB specific


class PerformanceEvent(BaseEntity):
    entity_type: str = "PerformanceEvent"
    # From PerformanceEvent mappings
    # object_properties: hasTimeInterval (TimeInterval identifier), involvesAgent (-> Artist identifiers?)
    # data_properties: name, description, hasEventDate (covered by TimeInterval)
    hasTimeInterval: Optional[str] = Field(
        None, description="Identifier of the TimeInterval entity for the event duration"
    )
    # Mappings are generic (involvesAgent). Add specific common properties:
    eventLocation: Optional[str] = Field(
        None, description="Identifier of the Place where the event occurred"
    )
    performedBy: Optional[List[str]] = Field(
        None, description="List of identifiers for performers (Musician/MusicEnsemble)"
    )
    involvesAgent: Optional[List[str]] = Field(
        None,
        description="List of identifiers for agents (performers) involved (Musician/MusicEnsemble)",
    )
    # MB specific fields
    cancelled: Optional[bool] = Field(
        None, description="Whether the event was cancelled (from MB)"
    )
    setlist: Optional[str] = Field(
        None, description="Setlist information (from MB, often textual)"
    )


# Helper to get model class from entity_type string (if needed later)
MODEL_MAP = {
    "Musician": Musician,
    "MusicEnsemble": MusicEnsemble,
    "Instrument": Instrument,
    "MusicGenre": MusicGenre,
    "Album": Album,
    "Single": Single,
    "PerformanceEvent": PerformanceEvent,
    "Recording": Recording,
    "Place": Place,
    "Country": Country,
    "RecordLabel": RecordLabel,
    "TimeInterval": TimeInterval,
    "MusicEnsembleMembership": MusicEnsembleMembership,
}
