package autotest.tko;

import autotest.tko.TkoUtils.FieldInfo;

import java.util.AbstractCollection;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

/**
 * A modifiable Collection of HeaderFields indexed by both field name and field SQL name.
 */
public class HeaderFieldCollection extends AbstractCollection<HeaderField> {
    private Map<String, HeaderField> fieldsByName = new HashMap<String, HeaderField>();
    private Map<String, HeaderField> fieldsBySqlName = new HashMap<String, HeaderField>();

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

        fieldsByName.put(field.name, field);
        fieldsBySqlName.put(field.sqlName, field);
        return true;
    }

    /**
     * We perform strict consistency checking here, and both add() and remove() use this.
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
            assert fieldsByName.get(field.getName()) == fieldsBySqlName.get(field.getSqlName());
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
        final Iterator<HeaderField> baseIterator = fieldsByName.values().iterator();
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
                fieldsBySqlName.remove(lastElement.getName());
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
    
    public boolean containsSqlName(String sqlName) {
        return fieldsBySqlName.containsKey(sqlName);
    }

    @Override
    public boolean remove(Object o) {
        if (!contains(o)) {
            return false;
        }

        HeaderField field = (HeaderField) o;
        fieldsByName.remove(field.getName());
        fieldsBySqlName.remove(field.getSqlName());
        return true;
    }
}
