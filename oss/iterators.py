# -*- coding: utf-8 -*-

"""
oss.iterators
~~~~~~~~~~~~~

该模块包含了一些易于使用的迭代器，可以用来遍历Bucket、对象、分片上传等。
"""

from . models import MultipartUploadInfo, SimplifiedObjectInfo


class _BaseIterator(object):
    def __init__(self, marker):
        self.is_truncated = True
        self.next_marker = marker

        self.entries = []

    def _fetch(self):
        raise NotImplemented

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            if self.entries:
                return self.entries.pop(0)

            if not self.is_truncated:
                raise StopIteration

            self.is_truncated, self.next_marker = self._fetch()

    def next(self):
        return self.__next__()


class BucketIterator(_BaseIterator):
    """遍历用户Bucket的迭代器。每次迭代返回的是 :class:`SimplifiedBucketInfo <oss.models.SimplifiedBucketInfo>` 对象。

    :param service: :class:`Service <oss.api.Service>` 对象
    :param prefix: 只列举匹配该前缀的Bucket
    :param marker: 分页符。只列举Bucket名字典序在此之后的Bucket
    :param max_keys: 每次调用 `list_buckets` 时的max_keys参数。注意迭代器返回的数目可能会大于该值。
    """
    def __init__(self, service, prefix='', marker='', max_keys=100):
        super(BucketIterator, self).__init__(marker)
        self.service = service
        self.prefix = prefix
        self.max_keys = max_keys

    def _fetch(self):
        result = self.service.list_buckets(prefix=self.prefix,
                                           marker=self.next_marker,
                                           max_keys=self.max_keys)
        self.entries = result.buckets

        return result.is_truncated, result.next_marker


class ObjectIterator(_BaseIterator):
    """遍历Bucket里对象的迭代器。每次迭代返回的是 :class:`SimplifiedObjectInfo <oss.models.SimplifiedObjectInfo>` 对象。

    :param bucket: :class:`Bucket <oss.api.Bucket>` 对象
    :param prefix: 只列举匹配该前缀的对象
    :param delimiter: 目录分隔符
    :param marker: 分页符
    :param max_keys: 每次调用 `list_objects` 时的max_keys参数。注意迭代器返回的数目可能会大于该值。
    """
    def __init__(self, bucket, prefix='', delimiter='', marker='', max_keys=100):
        super(ObjectIterator, self).__init__(marker)

        self.bucket = bucket
        self.prefix = prefix
        self.delimiter = delimiter
        self.max_keys = max_keys

    def _fetch(self):
        result = self.bucket.list_objects(prefix=self.prefix,
                                          delimiter=self.delimiter,
                                          marker=self.next_marker,
                                          max_keys=self.max_keys)
        self.entries = result.object_list + [SimplifiedObjectInfo(prefix, None, None, None, None)
                                             for prefix in result.prefix_list]
        self.entries.sort(key=lambda obj: obj.name)

        return result.is_truncated, result.next_marker


class MultipartUploadIterator(_BaseIterator):
    """遍历Bucket里未完成的分片上传。

    :param bucket: :class:`Bucket <oss.api.Bucket>` 对象
    :param prefix: 仅列举匹配该前缀的对象的分片上传
    :param delimiter: 目录分隔符
    :param key_marker: 对象名分页符
    :param upload_id_marker: 分片上传ID分页符
    :param max_uploads: 每次调用 `list_multipart_uploads` 时的max_uploads参数。注意迭代器返回的数目可能会大于该值。
    """
    def __init__(self, bucket, prefix='', delimiter='', key_marker='', upload_id_marker='', max_uploads=1000):
        super(MultipartUploadIterator, self).__init__(key_marker)

        self.bucket = bucket
        self.prefix = prefix
        self.delimiter = delimiter
        self.next_upload_id_marker = upload_id_marker
        self.max_uploads = max_uploads

    def _fetch(self):
        result = self.bucket.list_multipart_uploads(prefix=self.prefix,
                                                    delimiter=self.delimiter,
                                                    key_marker=self.next_marker,
                                                    upload_id_marker=self.next_upload_id_marker,
                                                    max_uploads=self.max_uploads)
        self.entries = result.upload_list + [MultipartUploadInfo(prefix, None, None) for prefix in result.prefix_list]
        self.entries.sort(key=lambda u: u.object_name)

        self.next_upload_id_marker = result.next_upload_id_marker
        return result.is_truncated, result.next_key_marker


class ObjectUploadIterator(_BaseIterator):
    def __init__(self, bucket, object_name):
        super(ObjectUploadIterator, self).__init__('')
        self.bucket = bucket
        self.object_name = object_name
        self.next_upload_id_marker = ''

    def _fetch(self):
        result = self.bucket.list_multipart_uploads(prefix=self.object_name,
                                                    key_marker=self.next_marker,
                                                    upload_id_marker=self.next_upload_id_marker)

        self.entries = [u for u in result.upload_list if u.object_name == self.object_name]
        self.next_upload_id_marker = result.next_upload_id_marker

        if not result.is_truncated or not self.entries:
            return False, result.next_key_marker

        if result.next_key_marker > self.object_name:
            return False, result.next_key_marker

        return result.is_truncated, result.next_key_marker


class PartIterator(_BaseIterator):
    """遍历一个分片上传会话中已经上传的分片。

    :param bucket: :class:`Bucket <oss.api.Bucket>` 对象
    :param object_name: 对象名
    :param upload_id: 分片上传ID
    :param marker: 分页符
    :param max_parts: 每次调用 `list_parts` 时的max_parts参数。注意迭代器返回的数目可能会大于该值。
    """
    def __init__(self, bucket, object_name, upload_id, marker='0', max_parts=1000):
        super(PartIterator, self).__init__(marker)

        self.bucket = bucket
        self.object_name = object_name
        self.upload_id = upload_id
        self.max_parts = max_parts

    def _fetch(self):
        result = self.bucket.list_parts(self.object_name, self.upload_id,
                                        marker=self.next_marker,
                                        max_parts=self.max_parts)
        self.entries = result.parts

        return result.is_truncated, result.next_marker
