from zkutils import (
    create,
    delete,
    get_val,
    set_val
)

create("/test1", "test2_value")
get_val("/test1")
