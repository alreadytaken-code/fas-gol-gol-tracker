KeyError: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).
Traceback:
File "/mount/src/fas-gol-gol-tracker/app.py", line 784, in <module>
    trend = build_trend_metrics(df)
File "/mount/src/fas-gol-gol-tracker/app.py", line 343, in build_trend_metrics
    blocks = build_blocks(df)
File "/mount/src/fas-gol-gol-tracker/app.py", line 328, in build_blocks
    grouped = valid_df.groupby(['group_key', 'cycle_id', 'giornata', 'group_label'], as_index=False).agg(
              ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.14/site-packages/pandas/util/_decorators.py", line 336, in wrapper
    return func(*args, **kwargs)
File "/home/adminuser/venv/lib/python3.14/site-packages/pandas/core/frame.py", line 10833, in groupby
    return DataFrameGroupBy(
        obj=self,
    ...<6 lines>...
        dropna=dropna,
    )
File "/home/adminuser/venv/lib/python3.14/site-packages/pandas/core/groupby/groupby.py", line 1095, in __init__
    grouper, exclusions, obj = get_grouper(
                               ~~~~~~~~~~~^
        obj,
        ^^^^
    ...<4 lines>...
        dropna=self.dropna,
        ^^^^^^^^^^^^^^^^^^^
    )
    ^
File "/home/adminuser/venv/lib/python3.14/site-packages/pandas/core/groupby/grouper.py", line 901, in get_grouper
    raise KeyError(gpr)
