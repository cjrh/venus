JSONB Tricks
------------

Extracting keys from a JSONB Column
===================================

https://www.reddit.com/r/PostgreSQL/comments/31q87a/get_keys_from_all_json_objects/

    This is mostly related to bad cardinality estimation. The planner does
    not have insight into how jsonb_object_keys works and so estimates that the
    number of distinct keys is the number of distinct values of the
    underlying column instead. For jsonb columns this is estimated to match
    the number of rows in the table. As a result the
    planner rejects the hash table approach as taking too much memory.

    Currently the only way to "hint" the planner here is
    to include non-constant tautological comparisons that reduce the row count
    estimate.

    If you do something like this you should get a hash aggregate
    without touching the work_mem setting:

    .. code-block:: sql

        select distinct jsonb_object_keys(col) as key
            from tbl
            where id = id;


        Wow, that really works, thanks! This way postgres uses
        hash aggregate, which performs ~20 times faster on my data
        (and gives the same result, of course). In this
        query almost the whole time is taken by table scan, so
        I think it is the optimal way. I wish there was
        a possibility to guide the planner in a more obvious way :)

Verified in Metabase:

.. code-block:: sql

    select distinct
      jsonb_object_keys(data)
    from logs
    where
      time = time
      and <constraint>

Returns all the keys.  The strategy for using this is the following:

0. Given a range constraint, provided by the user,
0. run the query above (including the constraint), obtain the keys
0. run the following query, using the keys obtained from the previous step:

    .. code-block:: sql

        select
          time,
          correlation_id,
          message,
          data->'key1' as "key1",
          data->'key2' as "key2",
          data->'key3' as "key3",
          <etc.>
        from logs
        where
          <constraint>

For records that lack some of the keys in the list, the above query will
return ``NULL`` in those fields for those records, so it's safe to run
on a dataset with different JSON structures in the ``data`` field.
