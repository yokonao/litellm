import json
from abc import abstractmethod
from typing import Optional, Union

import litellm
from litellm.types.utils import GenericStreamingChunk, ModelResponseStream


class BaseModelResponseIterator:
    def __init__(
        self, streaming_response, sync_stream: bool, json_mode: Optional[bool] = False
    ):
        self.streaming_response = streaming_response
        self.response_iterator = self.streaming_response
        self.json_mode = json_mode

    def chunk_parser(
        self, chunk: dict
    ) -> Union[GenericStreamingChunk, ModelResponseStream]:
        return GenericStreamingChunk(
            text="",
            is_finished=False,
            finish_reason="",
            usage=None,
            index=0,
            tool_use=None,
        )

    # Sync iterator
    def __iter__(self):
        return self

    def _handle_string_chunk(
        self, str_line: str
    ) -> Union[GenericStreamingChunk, ModelResponseStream]:
        # chunk is a str at this point

        stripped_chunk = litellm.CustomStreamWrapper._strip_sse_data_from_chunk(
            str_line
        )
        try:
            if stripped_chunk is not None:
                stripped_json_chunk: Optional[dict] = json.loads(stripped_chunk)
            else:
                stripped_json_chunk = None
        except json.JSONDecodeError:
            stripped_json_chunk = None

        if "[DONE]" in str_line:
            return GenericStreamingChunk(
                text="",
                is_finished=True,
                finish_reason="stop",
                usage=None,
                index=0,
                tool_use=None,
            )
        elif stripped_json_chunk:
            return self.chunk_parser(chunk=stripped_json_chunk)
        else:
            return GenericStreamingChunk(
                text="",
                is_finished=False,
                finish_reason="",
                usage=None,
                index=0,
                tool_use=None,
            )

    def __next__(self):
        try:
            chunk = self.response_iterator.__next__()
        except StopIteration:
            raise StopIteration
        except ValueError as e:
            raise RuntimeError(f"Error receiving chunk from stream: {e}")

        try:
            str_line = chunk
            if isinstance(chunk, bytes):  # Handle binary data
                str_line = chunk.decode("utf-8")  # Convert bytes to string
                index = str_line.find("data:")
                if index != -1:
                    str_line = str_line[index:]
            # chunk is a str at this point
            return self._handle_string_chunk(str_line=str_line)
        except StopIteration:
            raise StopIteration
        except ValueError as e:
            raise RuntimeError(f"Error parsing chunk: {e},\nReceived chunk: {chunk}")

    # Async iterator
    def __aiter__(self):
        self.async_response_iterator = self.streaming_response.__aiter__()
        return self

    async def __anext__(self):
        try:
            chunk = await self.async_response_iterator.__anext__()

        except StopAsyncIteration:
            raise StopAsyncIteration
        except ValueError as e:
            raise RuntimeError(f"Error receiving chunk from stream: {e}")

        try:
            str_line = chunk
            if isinstance(chunk, bytes):  # Handle binary data
                str_line = chunk.decode("utf-8")  # Convert bytes to string
                index = str_line.find("data:")
                if index != -1:
                    str_line = str_line[index:]

            # chunk is a str at this point
            chunk = self._handle_string_chunk(str_line=str_line)

            return chunk
        except StopAsyncIteration:
            raise StopAsyncIteration
        except ValueError as e:
            raise RuntimeError(f"Error parsing chunk: {e},\nReceived chunk: {chunk}")


class FakeStreamResponseIterator:
    def __init__(self, model_response, json_mode: Optional[bool] = False):
        self.model_response = model_response
        self.json_mode = json_mode
        self.is_done = False

    # Sync iterator
    def __iter__(self):
        return self

    @abstractmethod
    def chunk_parser(self, chunk: dict) -> GenericStreamingChunk:
        pass

    def __next__(self):
        if self.is_done:
            raise StopIteration
        self.is_done = True
        return self.chunk_parser(self.model_response)

    # Async iterator
    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.is_done:
            raise StopAsyncIteration
        self.is_done = True
        return self.chunk_parser(self.model_response)
