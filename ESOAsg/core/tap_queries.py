r"""Class to query the ESO archive

ESO DATA ACCESS POLICY
----------------------

The downloaded data are subject to the ESO Data Access Policy available here
`http://archive.eso.org/cms/eso-data-access-policy.html`

In particular, you are requested to acknowledge the usage of the ESO archive and of the ESO data; please refer to the
Acknowledgement policies section.

If you plan to redistribute the downloaded data, please refer to the "Requirements for third parties distributing ESO
data" section.
"""

from pyvo import dal

from ESOAsg import default
from ESOAsg import msgs

# currently supported tap services
TAP_SERVICES = ['eso_tap_cat', 'eso_tap_obs']


# I/O:

def define_tap_service(which_tap_service):
    r"""Load a Table Access Protocol (TAP) service from defaults

    Currently the supported `TAP services<http://archive.eso.org/programmatic/#TAP>`_ are:
    * `eso_tap_cat`: TAP service for scientific catalogues generated by ESO observing teams
    * `eso_tap_obs`: TAP service for raw, reduced, and ambient data

    See `pyvo docs<https://pyvo.readthedocs.io/en/latest/api/pyvo.dal.TAPService.html#>`_ for further details

    Args:
        which_tap_service (`str`): Select the `TAP services<http://archive.eso.org/programmatic/#TAP>`_ to be queried

    Returns:
        tap_service (`pyvo.dal.tap.TAPService`): TAP service used for the queries

    """
    if which_tap_service not in TAP_SERVICES:
        msgs.error('{} not a valid entry for TAP services. Possibilities are: {}'.format(which_tap_service,
                                                                                         TAP_SERVICES))
    tap_service = dal.tap.TAPService(default.get_value(which_tap_service))
    return tap_service


def print_query(query):
    r"""Print the query on the terminal

    In case the `query` is empty, a warning is raised

    Args:
        query (`str`): String containing the query

    Returns:
          None
    """
    if query is None:
        msgs.warning('The query is empty')
    else:
        msgs.info('The query is:')
        msgs.info('{}'.format(query))
    return


def which_service(tap_service):
    r"""Print a summary description of the TAP service used

    Args:
        tap_service (`pyvo.dal.tap.TAPService`): TAP service used for the queries

    Returns:
        None

    """
    msgs.info('The TAP service used is:')
    tap_service.describe()
    return


def run_query(tap_service, query, maxrec=default.get_value('maxrec')):
    r"""Run query to TAP service and return result as an `astropy.Table`

    Args:
        tap_service (`pyvo.dal.tap.TAPService`): TAP service that will be used for the query
        query (`str`): query to be run
        maxrec (`int`, optional): define the maximum number of entries that a single query can return. Default is set
            by default.get_value('maxrec')

    Returns:
        result_from_query (`astropy.Table`): result from the query to the TAP service
    """
    # Obtaining query results and convert it to an astropy table
    if query is not None:
        result_from_query = tap_service.search(query=query, maxrec=maxrec).to_table()
    else:
        msgs.warning('Empty query provided')
        result_from_query = None
    return result_from_query

# Query builders:
# This part of the module create some TAP queries to explore catalogues and observations

# Catalogues:


def create_query_all_catalogues(all_versions=False):
    r"""Create TAP query that returns info on all catalogues in the ESO archive

    Args:
        all_versions (`bool`): if set to `True` also obsolete versions of the catalogues are listed

    Returns:
        query_all_catalogues (`str`): string containing the query to obtain all catalogues present in the ESO archive

    """
    query_all_catalogues = '''
        SELECT 
            collection, title, version, table_name, filter, instrument, telescope, publication_date, 
            ref.description as description, number_rows, number_columns, rel_descr_url, acknowledgment, cat_id, 
            mjd_obs, mjd_end, skysqdeg, bibliography, document_id,
            kc.from_column as from_column, k.target_table as target_table, kc.target_column as target_column
        FROM
            TAP_SCHEMA.tables as ref
        LEFT OUTER JOIN 
            TAP_SCHEMA.keys as k on ref.table_name = k.from_table 
        AND
            k.target_table in (SELECT
                                    T.table_name
                                FROM 
                                    TAP_SCHEMA.tables as T
                                WHERE 3 in (SELECT 
                                                count(*) 
                                            FROM
                                                TAP_SCHEMA.columns
                                            WHERE
                                                table_name=T.table_name
                                            AND
                                                (ucd = 'pos.eq.ra;meta.main' OR
                                                 ucd = 'pos.eq.dec;meta.main' OR
                                                 ucd = 'meta.id;meta.main')
                                            )
                                )
        LEFT OUTER JOIN 
            TAP_SCHEMA.key_columns as kc on k.key_id=kc.key_id'''

    if not all_versions:
        query_last_version_only = '''
            WHERE
                cat_id in (SELECT
                                cat_id
                           FROM (SELECT
                                    t1.cat_id cat_id
                                 FROM
                                    TAP_SCHEMA.tables t1
                                 LEFT OUTER JOIN
                                    TAP_SCHEMA.tables t2 on (t1.title = t2.title and t1.version < t2.version)
                                 WHERE
                                    t2.title is null
                                )
                            t)'''
        query_all_catalogues = query_all_catalogues + query_last_version_only

    return query_all_catalogues

# Observations


def create_query_obscore_base():
    r"""Create the base string for a query to `ivoa.ObsCore`

    Returns:
        query (`str`):
            Base for the `ivoa.ObsCore` query::

                SELECT
                    target_name, dp_id, s_ra, s_dec, t_exptime, em_min, em_max, dataproduct_type, instrument_name,
                    obstech, abmaglim, proposal_id, obs_collection
                FROM
                    ivoa.ObsCore

    """
    query_base = '''
            SELECT
                target_name, dp_id, s_ra, s_dec, t_exptime, em_min, em_max, 
                dataproduct_type, instrument_name, obstech, abmaglim,
                proposal_id, obs_collection
            FROM
                ivoa.ObsCore'''
    return query_base


def condition_query_obscore_intersect_ra_dec(ra, dec, radius=None):
    r"""Create the where condition string for a query to `ivoa.ObsCore`

    Args:
        ra (`float`):
            RA of the target in degrees and in the ICRS system
        dec (`float`):
            Dec of the target in degrees and in the ICRS system
        radius (`float`):
            Search radius in arcsec. If set to `None` no radius will be considered in the INTERSECT condition
    Returns:
        query_intersect_ra_dec (`str`):
            String containing the WHERE INTERSECT condition for a query
    """
    if radius is None:
        query_intersect_ra_dec = '''
            WHERE
                INTERSECTS(POINT('ICRS',{},{}), s_region)=1'''.format(str(ra), str(dec))
    else:
        query_intersect_ra_dec = '''
            WHERE
                INTERSECTS(s_region,CIRCLE('ICRS',{},{},{}/3600.))=1'''.format(str(ra), str(dec), str(radius))
    return query_intersect_ra_dec


def condition_query_obscore_select_instruments(instruments_list):
    r"""Create condition string to select only specific instruments in `ivoa.ObsCore`

    Args:
        instruments_list (`list'):
            Limit the search to the selected list of instruments (e.g., `XSHOOTER`)
    Returns:
        query_select_instruments (`str`):
            String containing the `instrument_name=` condition for a query
    """
    if len(instruments_list) == 1:
        query_select_instruments = '''
            AND
                instrument_name='{}' '''.format(instruments_list[0])
    else:
        query_select_instruments = '''
            AND
                ('''
        for instrument_name in instruments_list:
            query_select_instruments = query_select_instruments + '''instrument_name='{}' OR '''.format(
                instrument_name)
        query_select_instruments = query_select_instruments[0:-4] + ')'
    return query_select_instruments


def condition_query_obscore_select_data_types(data_types_list):
    r"""Create condition string to select only specific dataproduct types in `ivoa.ObsCore`

    Args:
        data_types_list (`list'):
            Limit the search to the selected list of dataproduct types (e.g., `spectrum`)
    Returns:
        query_select_data_types (`str`):
            String containing the `dataproduct_type=` condition for a query
    """
    if len(data_types_list) == 1:
        query_select_data_types = '''
            AND
                dataproduct_type='{}' '''.format(data_types_list[0])
    else:
        query_select_data_types = '''
            AND
                ('''
        for data_type in data_types_list:
            query_select_data_types = query_select_data_types + '''dataproduct_type='{}' OR '''.format(data_type)
        query_select_data_types = query_select_data_types[0:-4] + ')'
    return query_select_data_types



