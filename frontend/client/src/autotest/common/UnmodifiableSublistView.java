package autotest.common;

import java.util.AbstractList;
import java.util.List;

public class UnmodifiableSublistView<T> extends AbstractList<T> {
    protected List<T> backingList;
    protected int start, size;
    
    public UnmodifiableSublistView(List<T> list, int start, int size) {
        assert start >= 0;
        assert size >= 0;
        assert start + size <= list.size();
        
        this.backingList = list;
        this.start = start;
        this.size = size;
    }

    @Override
    public T get(int arg0) {
        if (arg0 >= size())
            throw new IndexOutOfBoundsException();
        return backingList.get(arg0 + start);
    }

    @Override
    public int size() {
        return this.size;
    }
}
