package autotest.common;

import java.util.ArrayList;
import java.util.List;

public class SimpleChangeListenerCollection {
    private Object source;
    private List<SimpleChangeListener> listeners = new ArrayList<SimpleChangeListener>();

    public SimpleChangeListenerCollection(Object source) {
        this.source = source;
    }

    public void add(SimpleChangeListener listener) {
        listeners.add(listener);
    }

    public void notifyListeners() {
        for (SimpleChangeListener listener : listeners) {
            listener.onChange(source);
        }
    }
}
