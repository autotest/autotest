package afeclient.client;

import java.util.AbstractList;
import java.util.List;

public class UnmodifiableSublistView extends AbstractList {
    protected List backingList;
    protected int start, size;
    
    public UnmodifiableSublistView(List list, int start, int size) {
        assert start >= 0;
        assert size >= 0;
        assert start + size <= list.size();
        
        this.backingList = list;
        this.start = start;
        this.size = size;
    }

    public Object get(int arg0) {
        if (arg0 >= size())
            throw new IndexOutOfBoundsException();
        return backingList.get(arg0 + start);
    }

    public int size() {
        return this.size;
    }
}
