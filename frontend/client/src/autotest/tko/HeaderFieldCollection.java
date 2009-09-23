package autotest.tko;

import autotest.tko.TkoUtils.FieldInfo;

import java.util.AbstractCollection;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

/**
 * A modifiable, ordered Collection of unique HeaderFields indexed by both field name and field SQL 
 * name.
 */
public class HeaderFieldCollection extends AbstractCollection<HeaderField> {
    private Map<String, HeaderField> fieldsByName = new HashMap<String, HeaderField>();
    private Map<String, HeaderField> fieldsBySqlName = new HashMap<String, HeaderField>();
    private List<HeaderField> orderedFields = new ArrayList<HeaderField>();

    public void populateFromList(String fieldListName) {
        for (FieldInfo fieldInfo : TkoUtils.getFieldList(fieldListName)) {
            HeaderField field = new SimpleHeaderField(fieldInfo.name, fieldInfo.field);
            add(field);
        }
    }

    @Override
    public boolean add(HeaderField field) {
        if (contains(field)) {
            return false;
        }

        orderedFields.add(field);
        fieldsByName.put(field.getName(), field);
        fieldsBySqlName.put(field.getSqlName(), field);
        assert checkConsistency();
        return true;
    }

    /**
     * Called only within an assertion.
     */
    public boolean checkConsistency() {
        assert fieldsByName.size() == fieldsBySqlName.size();
        assert fieldsByName.size() == orderedFields.size();
        for (HeaderField field : fieldsByName.values()) {
            assert fieldsByName.get(field.getName()) == field;
            assert fieldsBySqlName.get(field.getSqlName()) == field;
            assert orderedFields.contains(field);
        }
        return true;
    }

    /**
     * We perform strict input checking here, and both add() and remove() use this.
     */
    @Override
    public boolean contains(Object o) {
        if (o == null || !(o instanceof HeaderField)) {
            return false;
        }

        HeaderField field = (HeaderField) o;
        boolean containsName = fieldsByName.containsKey(field.getName());
        boolean containsSqlName = fieldsBySqlName.containsKey(field.getSqlName());

        if (containsName && containsSqlName) {
            return true;
        }
        if (!containsName && containsSqlName) {
            throw new IllegalArgumentException("Duplicate SQL name: " + field + ", " 
                                               + fieldsBySqlName.get(field.getSqlName()));
        }
        if (containsName && !containsSqlName) {
            throw new IllegalArgumentException("Duplicate name: " + field + ", "
                                               + fieldsByName.get(field.getName()));
        }
        return false;
    }

    @Override
    public Iterator<HeaderField> iterator() {
        final Iterator<HeaderField> baseIterator = orderedFields.iterator();
        return new Iterator<HeaderField>() {
            HeaderField lastElement;

            @Override
            public boolean hasNext() {
                return baseIterator.hasNext();
            }

            @Override
            public HeaderField next() {
                lastElement = baseIterator.next();
                return lastElement;
            }

            @Override
            public void remove() {
                baseIterator.remove();
                fieldsByName.remove(lastElement.getName());
                fieldsBySqlName.remove(lastElement.getSqlName());
                assert checkConsistency();
            }
        };
    }

    @Override
    public int size() {
        return fieldsByName.size();
    }

    public HeaderField getFieldByName(String name) {
        assert fieldsByName.containsKey(name) : name;
        return fieldsByName.get(name);
    }

    public HeaderField getFieldBySqlName(String sqlName) {
        assert fieldsBySqlName.containsKey(sqlName) : sqlName;
        return fieldsBySqlName.get(sqlName);
    }

    public boolean containsName(String name) {
        return fieldsByName.containsKey(name);
    }
    
    public boolean containsSqlName(String sqlName) {
        return fieldsBySqlName.containsKey(sqlName);
    }

    /**
     * Note this is O(n).
     */
    @Override
    public boolean remove(Object o) {
        if (!contains(o)) {
            return false;
        }

        HeaderField field = (HeaderField) o;
        orderedFields.remove(field);
        fieldsByName.remove(field.getName());
        fieldsBySqlName.remove(field.getSqlName());
        return true;
    }

    void addHistoryArguments(Map<String, String> arguments) {
        for (HeaderField field : this) {
            field.addHistoryArguments(arguments);
        }
    }

    public void handleHistoryArguments(Map<String, String> arguments) {
        for (HeaderField field : this) {
            field.handleHistoryArguments(arguments);
        }
    }
}
