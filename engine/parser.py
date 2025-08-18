from io import BytesIO, StringIO
from typing import List, Tuple, Union, IO
...
def load_csv(src: Union[str, BytesIO, StringIO, IO[str]]) -> Tuple[pd.DataFrame, List[str]]:
    df = pd.read_csv(src)
    ...

