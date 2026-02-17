from autosedance.state.schema import SegmentRecord, merge_segments


def test_merge_segments_overwrites_by_index_and_sorts():
    left = [
        SegmentRecord(index=1, segment_script="a1", video_prompt="p1"),
        SegmentRecord(index=0, segment_script="a0", video_prompt="p0"),
    ]
    right = [
        SegmentRecord(index=1, segment_script="b1", video_prompt="q1"),
        SegmentRecord(index=2, segment_script="b2", video_prompt="q2"),
    ]

    merged = merge_segments(left, right)
    assert [s.index for s in merged] == [0, 1, 2]
    assert merged[1].segment_script == "b1"
    assert merged[1].video_prompt == "q1"

